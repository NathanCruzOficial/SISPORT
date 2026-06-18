# =====================================================================
# visitor_views.py
# Views (Rotas) de Visitantes — Define todas as rotas do Blueprint
# de visitantes, incluindo: identificação por CPF, wizard de cadastro
# (3 etapas), check-in/check-out, foto via banco, relatórios,
# edição/exclusão de visitantes e rotas internas.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    Response,
)

from ..extensions import db
from ..models.visitor import Visitor, Visit, TempPhoto
from ..controllers.visitor_controller import (
    find_visitor_by_cpf,
    wizard_start_for_new_visitor,
    wizard_step1_submit,
    wizard_step2_submit,
    create_visitor_if_not_exists_from_wizard,
    register_checkin,
    checkout_visit,
    visitor_photo_update,
    _check_duplicate_fields,
)
from ..models.visitor_destination import VisitorDestinationGroup, VisitorDestinationPlace
from ..models.settings import get_setting

from ..utils.validators import normalize_cpf, is_valid_cpf, validate_required_email
from sqlalchemy.exc import IntegrityError

from calendar import monthrange
from collections import Counter
from datetime import date, datetime, timedelta




# ─────────────────────────────────────────────────────────────────────
# Blueprint + Context Processor
# ─────────────────────────────────────────────────────────────────────

visitor_bp = Blueprint("visitor", __name__)


@visitor_bp.app_context_processor
def inject_photo_helper():
    """
    Injeta a função photo_url() em TODOS os templates.
    Uso: <img src="{{ photo_url('visitor', visitor.id) }}">
         <img src="{{ photo_url('temp', temp_id) }}">
    """
    from time import time

    def photo_url(source, record_id):
        return url_for(
            "visitor.serve_photo", source=source, record_id=str(record_id)
        ) + f"?t={int(time())}"

    return {"photo_url": photo_url}

# =====================================================================
# Helpers — Destinos de visita
# =====================================================================

def _visit_reason_required() -> bool:
    """
    Retorna se o motivo da visita é obrigatório conforme configurações.
    """
    return str(get_setting("visitor_visit_reason_required", "0")) == "1"


def _build_destination_tree():
    """
    Monta uma árvore com grupos e locais ativos para seleção rápida no check-in.

    Retorno:
    [
        {
            "id": 1,
            "name": "Raiz",
            "color": "#ffc107",
            "is_root": True,
            "places": [...],
            "children": [...]
        }
    ]
    """
    root = VisitorDestinationGroup.query.filter_by(is_root=True).first()

    if not root:
        return []

    def build_group(group):
        places = (
            VisitorDestinationPlace.query
            .filter_by(group_id=group.id, is_active=True)
            .order_by(
                VisitorDestinationPlace.sort_order.asc(),
                VisitorDestinationPlace.name.asc(),
            )
            .all()
        )

        children = (
            VisitorDestinationGroup.query
            .filter_by(parent_id=group.id)
            .order_by(
                VisitorDestinationGroup.sort_order.asc(),
                VisitorDestinationGroup.name.asc(),
            )
            .all()
        )

        return {
            "id": group.id,
            "name": group.name,
            "color": group.color or "#198754",
            "is_root": group.is_root,
            "places": places,
            "children": [build_group(child) for child in children],
        }

    return [build_group(root)]


def _get_selected_destination_from_form():
    """
    Lê o local selecionado no formulário e retorna o nome do destino.
    """
    place_id = request.form.get("destination_place_id", type=int)

    if not place_id:
        raise ValueError("Selecione o local/destino da visita.")

    place = VisitorDestinationPlace.query.filter_by(
        id=place_id,
        is_active=True,
    ).first()

    if not place:
        raise ValueError("Local/destino inválido ou inativo.")

    return place.name


def _get_reason_from_form():
    """
    Lê o motivo da visita e valida conforme configuração.
    """
    reason = (request.form.get("reason") or "").strip()

    if _visit_reason_required() and not reason:
        raise ValueError("Informe o motivo da visita.")

    return reason


# =====================================================================
# Rotas — Identificação por CPF (Tela Inicial)
# =====================================================================

@visitor_bp.route("/", methods=["GET"])
def identify():
    """
    Renderiza a tela inicial de identificação por CPF.
    Inclui dados de status geral e lista de visitas em aberto.
    """
    open_list = (
        db.session.query(Visit)
        .filter(Visit.check_out.is_(None))
        .order_by(Visit.check_in.desc())
        .all()
    )

    today = date.today()
    today_visits = (
        db.session.query(Visit)
        .filter(db.func.date(Visit.check_in) == today)
        .all()
    )

    checked_out_today = sum(1 for v in today_visits if v.check_out is not None)
    total_visitors = db.session.query(Visitor).count()

    return render_template(
        "identify.html",
        open_visits=open_list,
        open_count=len(open_list),
        today_count=len(today_visits),
        checked_out_today=checked_out_today,
        total_visitors=total_visitors,
    )


@visitor_bp.route("/identify", methods=["POST"])
def identify_post():
    """
    Processa o formulário de identificação por CPF.
    """
    raw_cpf = request.form.get("cpf", "")
    cpf = normalize_cpf(raw_cpf)

    if not is_valid_cpf(cpf):
        flash("CPF inválido. Verifique e tente novamente.", "danger")
        return redirect(url_for("visitor.identify"))

    v = find_visitor_by_cpf(cpf)
    if v:
        return redirect(url_for("visitor.checkin_form", visitor_id=v.id))

    wizard_start_for_new_visitor(cpf=cpf)
    return redirect(url_for("visitor.wizard"))


# =====================================================================
# Rotas — Check-in / Check-out de Visitas
# =====================================================================

@visitor_bp.route("/checkin/<int:visitor_id>", methods=["GET", "POST"])
def checkin_form(visitor_id: int):
    """
    Exibe formulário de check-in ou registra a entrada.
    """
    visitor = db.session.get(Visitor, visitor_id)

    if not visitor:
        flash("Visitante não encontrado.", "danger")
        return redirect(url_for("visitor.identify"))

    if request.method == "POST":
        try:
            destination = _get_selected_destination_from_form()
            reason = _get_reason_from_form()

            visit_id = register_checkin(
                visitor=visitor,
                destination=destination,
                reason=reason,
            )

            flash(f"Entrada registrada (visita {visit_id}).", "success")
            return redirect(url_for("visitor.identify"))

        except Exception as e:
            flash(str(e), "danger")

    return render_template(
        "checkin_existing.html",
        visitor=visitor,
        destination_tree=_build_destination_tree(),
        visit_reason_required=_visit_reason_required(),
    )


@visitor_bp.route("/checkout/<int:visit_id>", methods=["POST"])
def checkout(visit_id: int):
    """
    Registra a saída (check-out) de uma visita em aberto.
    """
    try:
        checkout_visit(visit_id)
        flash("Saída registrada.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.open_visits"))


# =====================================================================
# Rotas — Wizard de Cadastro (Etapas 1 → 2 → 3/Finish)
# =====================================================================

@visitor_bp.route("/wizard", methods=["GET"])
def wizard():
    """
    Exibe o wizard de 3 etapas para novo cadastro de visitante.
    """
    if "wizard" not in session:
        wizard_start_for_new_visitor()

    return render_template(
        "visitor_wizard.html",
        wizard=session["wizard"],
        destination_tree=_build_destination_tree(),
        visit_reason_required=_visit_reason_required(),
    )



@visitor_bp.route("/wizard/step1", methods=["POST"])
def wizard_step1():
    """
    Processa a Etapa 1 do wizard (dados pessoais).
    """
    try:
        wizard_step1_submit(
            request.form.get("name", ""),
            request.form.get("father_name", ""),
            request.form.get("mom_name", ""),
            request.form.get("cpf", ""),
            request.form.get("phone", ""),
            request.form.get("email", ""),
            request.form.get("empresa", ""),
            request.form.get("category", "civil"),
        )
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/step2", methods=["POST"])
def wizard_step2():
    """
    Processa a Etapa 2 do wizard: foto do visitante.
    """
    skip = request.form.get("skip")
    photo_data_url = None if skip else (request.form.get("photo_data_url") or "")
    try:
        wizard_step2_submit(photo_data_url)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/back/<int:step>", methods=["GET"])
def wizard_back(step: int):
    """Volta o wizard para a etapa indicada, sem perder dados."""
    w = session.get("wizard")
    if not w:
        return redirect(url_for("visitor.identify"))

    target = max(1, min(step, w.get("step", 1)))
    w["step"] = target
    session["wizard"] = w
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/finish", methods=["POST"])
def wizard_finish():
    """
    Etapa final do wizard: cria o visitante e registra check-in.
    """
    try:
        visitor = create_visitor_if_not_exists_from_wizard()

        destination = _get_selected_destination_from_form()
        reason = _get_reason_from_form()

        register_checkin(
            visitor=visitor,
            destination=destination,
            reason=reason,
        )

        flash("Visitante cadastrado e check-in registrado!", "success")

        session.pop("wizard", None)

        return redirect(url_for("visitor.identify"))

    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("visitor.wizard"))




# =====================================================================
# Rota ÚNICA — Foto (servida do banco de dados)
# =====================================================================

@visitor_bp.route("/photo/<string:source>/<string:record_id>", methods=["GET"])
def serve_photo(source, record_id):
    """
    Rota única para servir qualquer foto do sistema como BLOB.

    Fontes suportadas:
        /photo/visitor/42      → foto definitiva do visitante
        /photo/temp/abc123     → foto temporária do wizard
    """
    photo_data = None
    photo_mime = None

    if source == "visitor":
        visitor = db.session.get(Visitor, int(record_id))
        if visitor:
            photo_data = visitor.photo_data
            photo_mime = visitor.photo_mimetype

    elif source == "temp":
        photo = db.session.get(TempPhoto, record_id)
        if photo:
            photo_data = photo.photo_data
            photo_mime = photo.photo_mimetype

    if not photo_data:
        abort(404)

    return Response(
        photo_data,
        mimetype=photo_mime or "image/jpeg",
        headers={"Cache-Control": "no-store"},
    )

# =====================================================================
# Rotas — Dashboard
# =====================================================================

@visitor_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Dashboard gerencial com indicadores e gráficos de visitas.
    Usa filtros por ano e mês.
    """

    dashboard_data = _build_dashboard_data()

    return render_template(
        "dashboard.html",
        title="Dashboard",
        **dashboard_data,
    )


@visitor_bp.route("/dashboard/print", methods=["GET"])
def dashboard_print():
    """
    Versão de impressão do Dashboard.
    Usa os mesmos filtros da tela principal.
    """

    dashboard_data = _build_dashboard_data()

    return render_template(
        "dashboard_print.html",
        title="Impressão do Dashboard",
        generated_at=datetime.now(),
        **dashboard_data,
    )


def _build_dashboard_data():
    """
    Monta todos os dados necessários para o Dashboard e para a impressão.

    Filtros:
    - year: ano selecionado.
    - month: mês final do período.
        0 = todos os meses disponíveis do ano.
        1..12 = de janeiro até o mês selecionado.

    Exemplo:
    year=2026, month=5
    Resultado: período de 01/01/2026 até 31/05/2026,
    ou até a data atual se for o ano/mês corrente.
    """

    today = date.today()

    meses_nomes = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]

    # ─────────────────────────────────────────────────────────────
    # Anos disponíveis
    # ─────────────────────────────────────────────────────────────
    year_rows = (
        db.session.query(db.extract("year", Visit.check_in))
        .filter(Visit.check_in.isnot(None))
        .distinct()
        .all()
    )

    anos_disponiveis = sorted(
        {int(row[0]) for row in year_rows if row[0] is not None},
        reverse=True,
    )

    if not anos_disponiveis:
        anos_disponiveis = [today.year]

    # ─────────────────────────────────────────────────────────────
    # Filtros recebidos pela URL
    # ─────────────────────────────────────────────────────────────
    try:
        selected_year = int(request.args.get("year", today.year))
    except ValueError:
        selected_year = today.year

    if selected_year not in anos_disponiveis:
        selected_year = anos_disponiveis[0]

    try:
        selected_month = int(request.args.get("month", 0))
    except ValueError:
        selected_month = 0

    if selected_month < 0 or selected_month > 12:
        selected_month = 0

    # Evita selecionar mês futuro no ano atual
    if selected_year == today.year and selected_month > today.month:
        selected_month = today.month

    # ─────────────────────────────────────────────────────────────
    # Período filtrado
    #
    # month = 0  → ano inteiro
    # month = 1  → somente janeiro
    # month = 2  → somente fevereiro
    # ...
    # month = 12 → somente dezembro
    # ─────────────────────────────────────────────────────────────
    if selected_month == 0:
        dt_from = date(selected_year, 1, 1)

        if selected_year == today.year:
            dt_to = today
        else:
            dt_to = date(selected_year, 12, 31)
    else:
        dt_from = date(selected_year, selected_month, 1)

        last_day = monthrange(selected_year, selected_month)[1]
        dt_to = date(selected_year, selected_month, last_day)

        # Se for o mês atual, limita até hoje
        if selected_year == today.year and selected_month == today.month:
            dt_to = today


    # ─────────────────────────────────────────────────────────────
    # Consulta das visitas no período
    # ─────────────────────────────────────────────────────────────
    visits = (
        db.session.query(Visit)
        .join(Visitor, Visit.visitor_id == Visitor.id)
        .filter(db.func.date(Visit.check_in) >= dt_from)
        .filter(db.func.date(Visit.check_in) <= dt_to)
        .order_by(Visit.check_in.asc())
        .all()
    )

    total_visits = len(visits)

    total_visitors = db.session.query(Visitor).count()


    closed_visits = [
        v for v in visits
        if v.check_out is not None
    ]


    # ─────────────────────────────────────────────────────────────
    # Detalhamento das visitas para análise dos gráficos
    # Usado no Dashboard para abrir modal ao clicar em colunas/fatias
    # ─────────────────────────────────────────────────────────────
    visit_details = []

    for visit in visits:
        visitor_name = visit.visitor.name if visit.visitor else "Não informado"
        visitor_category = visit.visitor.category if visit.visitor else "civil"

        check_in = visit.check_in
        check_out = visit.check_out

        duration = "-"

        if check_in and check_out:
            duration_seconds = int((check_out - check_in).total_seconds())
            duration = _format_seconds_hms(duration_seconds)

        visit_details.append({
            "id": visit.id,
            "visitor_name": visitor_name,
            "category": visitor_category,
            "destination": (visit.destination or "Não informado").strip().upper(),
            "check_in": check_in.strftime("%d/%m/%Y %H:%M") if check_in else "-",
            "check_out": check_out.strftime("%d/%m/%Y %H:%M") if check_out else "Em aberto",
            "duration": duration,
            "month": check_in.month if check_in else None,
            "weekday": check_in.weekday() if check_in else None,
            "hour": check_in.hour if check_in else None,
        })

    # ─────────────────────────────────────────────────────────────
    # Tempo médio de permanência
    # ─────────────────────────────────────────────────────────────
    avg_seconds = 0

    if closed_visits:
        total_seconds = sum(
            int((v.check_out - v.check_in).total_seconds())
            for v in closed_visits
        )
        avg_seconds = int(total_seconds / len(closed_visits))

    avg_duration = _format_seconds_hms(avg_seconds)
    
    # ─────────────────────────────────────────────────────────────
    # Indicadores principais do Dashboard
    # Estrutura preparada para inclusão futura de novos indicadores
    # ─────────────────────────────────────────────────────────────
    dashboard_indicators = [
        {
            "label": "Visitas no período",
            "value": total_visits,
            "icon": "bi-calendar-check",
        },
        {
            "label": "Visitantes cadastrados",
            "value": total_visitors,
            "icon": "bi-person-vcard",
        },
        {
            "label": "Tempo médio",
            "value": avg_duration,
            "icon": "bi-clock-history",
        },
        # Futuramente, basta incluir novos itens aqui:
        # {
        #     "label": "Alterações",
        #     "value": total_alteracoes,
        #     "icon": "bi-exclamation-triangle",
        # },
        # {
        #     "label": "Objetos perdidos",
        #     "value": total_objetos_perdidos,
        #     "icon": "bi-box-seam",
        # },
    ]


    # ─────────────────────────────────────────────────────────────
    # Visitas por mês
    # ─────────────────────────────────────────────────────────────
    month_counter = Counter(
        v.check_in.month for v in visits
    )

    if selected_month == 0:
        months_to_show = list(range(1, dt_to.month + 1))
    else:
        months_to_show = [selected_month]


    visits_by_month_labels = [
        meses_nomes[m - 1] for m in months_to_show
    ]

    visits_by_month_values = [
        month_counter.get(m, 0) for m in months_to_show
    ]

    # ─────────────────────────────────────────────────────────────
    # Visitas por dia da semana
    # ─────────────────────────────────────────────────────────────
    weekday_names = [
        "Segunda",
        "Terça",
        "Quarta",
        "Quinta",
        "Sexta",
        "Sábado",
        "Domingo",
    ]

    weekday_counter = Counter(
        v.check_in.weekday() for v in visits
    )

    visits_by_weekday_labels = weekday_names

    visits_by_weekday_values = [
        weekday_counter.get(i, 0) for i in range(7)
    ]

    # ─────────────────────────────────────────────────────────────
    # Visitas por dia (usado quando um mês específico está filtrado)
    # ─────────────────────────────────────────────────────────────
    visits_by_day_labels = []
    visits_by_day_values = []

    if selected_month != 0:
        last_day = monthrange(selected_year, selected_month)[1]

        day_counter = Counter()

        for visit in visits:
            if visit.check_in and visit.check_in.month == selected_month:
                day_counter[visit.check_in.day] += 1

        for day in range(1, last_day + 1):
            visits_by_day_labels.append(f"{day:02d}")
            visits_by_day_values.append(day_counter.get(day, 0))


    # ─────────────────────────────────────────────────────────────
    # Destinos mais visitados
    # ─────────────────────────────────────────────────────────────
    destination_counter = Counter(
        (v.destination or "Não informado").strip().upper()
        for v in visits
    )

    top_destinations = destination_counter.most_common(10)

    top_destination_labels = [
        item[0] for item in top_destinations
    ]

    top_destination_values = [
        item[1] for item in top_destinations
    ]

    # ─────────────────────────────────────────────────────────────
    # Categorias de visitante
    # ─────────────────────────────────────────────────────────────
    category_labels_map = {
        "civil": "Civil",
        "militar": "Militar",
        "ex-militar": "Ex-Militar",
    }

    category_counter = Counter(
        v.visitor.category or "civil"
        for v in visits
    )

    ordered_categories = [
        "civil",
        "militar",
        "ex-militar",
    ]

    category_labels = [
        category_labels_map.get(category, category.capitalize())
        for category in ordered_categories
    ]

    category_values = [
        category_counter.get(category, 0)
        for category in ordered_categories
    ]

    unknown_categories_total = sum(
        count
        for category, count in category_counter.items()
        if category not in ordered_categories
    )

    if unknown_categories_total:
        category_labels.append("Outros")
        category_values.append(unknown_categories_total)

    # ─────────────────────────────────────────────────────────────
    # Média de pessoas presentes por horário
    # Considera o período entre check_in e check_out
    # ─────────────────────────────────────────────────────────────
    presence_by_hour_labels, presence_by_hour_values = _build_presence_by_hour(
        dt_from=dt_from,
        dt_to=dt_to,
    )


    # ─────────────────────────────────────────────────────────────
    # Texto do filtro
    # ─────────────────────────────────────────────────────────────
    if selected_month == 0:
        selected_month_name = "Todos"
        selected_period_label = f"Ano de {selected_year}"
    else:
        selected_month_name = meses_nomes[selected_month - 1]
        selected_period_label = f"{selected_month_name} de {selected_year}"


    filters = {
        "date_from": dt_from.strftime("%Y-%m-%d"),
        "date_to": dt_to.strftime("%Y-%m-%d"),
        "date_from_fmt": dt_from.strftime("%d/%m/%Y"),
        "date_to_fmt": dt_to.strftime("%d/%m/%Y"),
        "period_label": selected_period_label,
    }

    return {
        "filters": filters,

        "selected_year": selected_year,
        "selected_month": selected_month,
        "selected_month_name": selected_month_name,

        "anos_disponiveis": anos_disponiveis,
        "meses_nomes": meses_nomes,

        "dashboard_indicators": dashboard_indicators,

        "total_visits": total_visits,
        "total_visitors": total_visitors,
        "avg_duration": avg_duration,

        "visits_by_month_labels": visits_by_month_labels,
        "visits_by_month_values": visits_by_month_values,

        "visits_by_weekday_labels": visits_by_weekday_labels,
        "visits_by_weekday_values": visits_by_weekday_values,

        "visits_by_day_labels": visits_by_day_labels,
        "visits_by_day_values": visits_by_day_values,


        "top_destination_labels": top_destination_labels,
        "top_destination_values": top_destination_values,
        "top_destinations": top_destinations,

        "category_labels": category_labels,
        "category_values": category_values,

        "presence_by_hour_labels": presence_by_hour_labels,
        "presence_by_hour_values": presence_by_hour_values,

        "visit_details": visit_details
    }

def _build_presence_by_hour(dt_from: date, dt_to: date):
    """
    Calcula a média de pessoas presentes no aquartelamento por faixa horária.

    Diferente de contar apenas entradas por hora, esta função considera
    o período completo de permanência da pessoa:

    check_in até check_out.

    Resultado:
    - Labels: 00:00 até 23:00
    - Valores: média de pessoas presentes naquela hora ao longo do período
    """

    period_start = datetime.combine(dt_from, datetime.min.time())
    period_end = datetime.combine(dt_to, datetime.max.time())

    today = date.today()

    # Se o período inclui o dia atual, não faz sentido projetar até 23:59
    if dt_to >= today:
        period_end = min(period_end, datetime.now())

    overlapping_visits = (
        db.session.query(Visit)
        .filter(Visit.check_in <= period_end)
        .filter(
            db.or_(
                Visit.check_out.is_(None),
                Visit.check_out >= period_start,
            )
        )
        .all()
    )

    seconds_by_hour = [0 for _ in range(24)]

    for visit in overlapping_visits:
        start = max(visit.check_in, period_start)

        if visit.check_out:
            end = min(visit.check_out, period_end)
        else:
            end = period_end

        if end <= start:
            continue

        cursor = start

        while cursor < end:
            next_hour = (
                cursor
                .replace(minute=0, second=0, microsecond=0)
                + timedelta(hours=1)
            )

            segment_end = min(end, next_hour)

            seconds_by_hour[cursor.hour] += (
                segment_end - cursor
            ).total_seconds()

            cursor = segment_end

    days_count = max(1, (dt_to - dt_from).days + 1)

    labels = [
        f"{hour:02d}:00" for hour in range(24)
    ]

    values = [
        round((seconds / 3600) / days_count, 2)
        for seconds in seconds_by_hour
    ]

    return labels, values


def _format_seconds_hms(seconds: int) -> str:
    """
    Formata segundos em HH:MM:SS.
    """

    seconds = max(0, int(seconds))

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    return f"{h:02d}:{m:02d}:{s:02d}"


# =====================================================================
# Rotas — Visitas em Aberto
# =====================================================================

@visitor_bp.route("/open", methods=["GET"])
def open_visits():
    """
    Lista todas as visitas em aberto (sem check-out).
    """
    open_list = (
        db.session.query(Visit)
        .filter(Visit.check_out.is_(None))
        .order_by(Visit.check_in.asc())
        .all()
    )

    today = date.today()
    today_visits = (
        db.session.query(Visit)
        .filter(db.func.date(Visit.check_in) == today)
        .all()
    )
    checked_out_today = sum(1 for v in today_visits if v.check_out is not None)

    return render_template(
        "open_visits.html",
        visits=open_list,
        today_count=len(today_visits),
        checked_out_today=checked_out_today,
    )


# =====================================================================
# Rotas — Relatório Unificado com Filtros
# =====================================================================

@visitor_bp.route("/report", methods=["GET"])
def report_page():
    """Relatório unificado com filtros de período, busca, status e categoria."""
    visits, filters, dt_from, dt_to, open_ct, closed_ct = _build_report_query()

    today = date.today()
    if dt_from == dt_to == today:
        title = "Relatório de Hoje"
    elif dt_from == dt_to:
        title = f"Relatório — {dt_from.strftime('%d/%m/%Y')}"
    else:
        title = f"Relatório — {dt_from.strftime('%d/%m/%Y')} a {dt_to.strftime('%d/%m/%Y')}"

    return render_template(
        "report_page.html",
        visits=visits,
        title=title,
        filters=filters,
        total=len(visits),
        open_count=open_ct,
        closed_count=closed_ct,
    )


@visitor_bp.route("/report/print", methods=["GET"])
def report_print():
    """Versão para impressão do relatório."""
    visits, filters, dt_from, dt_to, open_count, closed_count = _build_report_query()

    return render_template(
        "print.html",
        visits=visits,
        today=date.today(),
        generated_at=datetime.now(),
        filters=filters,
        open_count=open_count,
        closed_count=closed_count,
    )

@visitor_bp.route("/report/today", methods=["GET"])
def report_today():
    """Redireciona para o relatório filtrado por hoje."""
    today = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("visitor.report_page", date_from=today, date_to=today))


@visitor_bp.route("/report/today/print")
def report_today_print():
    """Redireciona para impressão com filtro de hoje."""
    today = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("visitor.report_print", date_from=today, date_to=today))

# ─────────────────────────────────────────────────────────────────────
# Helper — Query de relatório com filtros (compartilhada)
# ─────────────────────────────────────────────────────────────────────

def _build_report_query():
    """
    Lê filtros da query string e retorna:
    (visits, filters, dt_from, dt_to, open_count, closed_count)
    """
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    search    = request.args.get("search", "").strip()
    status    = request.args.get("status", "all")
    category  = request.args.get("category", "all")

    today = date.today()
    try:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today
    except ValueError:
        dt_from = today
    try:
        dt_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    except ValueError:
        dt_to = today

    if dt_from > dt_to:
        dt_from, dt_to = dt_to, dt_from

    query = (
        db.session.query(Visit)
        .join(Visitor, Visit.visitor_id == Visitor.id)
        .filter(db.func.date(Visit.check_in) >= dt_from)
        .filter(db.func.date(Visit.check_in) <= dt_to)
    )

    if status == "open":
        query = query.filter(Visit.check_out.is_(None))
    elif status == "closed":
        query = query.filter(Visit.check_out.isnot(None))

    if category in ("civil", "militar", "ex-militar"):
        query = query.filter(Visitor.category == category)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Visitor.name.ilike(like),
                Visitor.cpf.like(like),
                Visit.destination.ilike(like),
                Visitor.phone.like(like),
            )
        )

    visits = query.order_by(Visit.check_in.desc()).all()

    open_count   = sum(1 for v in visits if v.check_out is None)
    closed_count = len(visits) - open_count

    filters = {
        "date_from":     dt_from.strftime("%Y-%m-%d"),
        "date_to":       dt_to.strftime("%Y-%m-%d"),
        "date_from_fmt": dt_from.strftime("%d/%m/%Y"),
        "date_to_fmt":   dt_to.strftime("%d/%m/%Y"),
        "search":        search,
        "status":        status,
        "category":      category,
    }

    return visits, filters, dt_from, dt_to, open_count, closed_count


# =====================================================================
# Rotas — Edição de Visitantes
# =====================================================================

@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["GET"])
def visitor_edit(visitor_id):
    """
    Exibe o formulário de edição de um visitante existente.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))
    return render_template("visitor_edit.html", visitor=v)


@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["POST"])
def visitor_edit_post(visitor_id):
    """
    Processa o formulário de edição de visitante.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    name        = (request.form.get("name") or "").strip().upper()
    phone       = (request.form.get("phone") or "").strip()
    mom_name    = (request.form.get("mom_name") or "").strip().upper()
    father_name = (request.form.get("father_name") or "").strip().upper()
    empresa     = (request.form.get("empresa") or "").strip().upper()
    category    = (request.form.get("category") or "civil").strip().lower()

    try:
        email = validate_required_email(request.form.get("email", ""))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))

    if not name:
        flash("Nome é obrigatório.", "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))
    if not phone:
        flash("Telefone é obrigatório.", "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))
    if not mom_name:
        flash("Nome da mãe é obrigatório.", "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))
    if category not in ("civil", "militar", "ex-militar"):
        flash("Categoria inválida.", "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))

    try:
        _check_duplicate_fields(
            name=name, father_name=father_name, mom_name=mom_name,
            cpf=v.cpf, phone=phone, email=email, exclude_id=v.id,
        )
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))

    v.name        = name
    v.phone       = phone
    v.email       = email
    v.mom_name    = mom_name
    v.father_name = father_name or None
    v.empresa     = empresa or None
    v.category    = category

    try:
        db.session.commit()
        flash("Cadastro atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao salvar: conflito de dados.", "danger")

    return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))


# =====================================================================
# Rotas — Atualização de Foto de Visitante
# =====================================================================

@visitor_bp.route("/visitors/<int:visitor_id>/photo", methods=["POST"])
def visitor_update_photo(visitor_id):
    """
    Recebe uma foto em data URL (base64) e salva como BLOB no banco.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    try:
        photo_url = request.form.get("photo_data_url", "")
        visitor_photo_update(v, photo_url)
        flash("Foto atualizada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))


# =====================================================================
# Rotas — Exclusão de Visitante
# =====================================================================

@visitor_bp.route("/visitors/<int:visitor_id>/delete", methods=["POST"])
def visitor_delete(visitor_id):
    """
    Exclui um visitante e todos os seus registros de visita.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    Visit.query.filter_by(visitor_id=v.id).delete()
    db.session.delete(v)
    db.session.commit()

    flash("Cadastro excluído.", "success")
    return redirect(url_for("visitor.identify"))


# =====================================================================
# Rotas Internas (somente acessíveis pelo próprio sistema)
# =====================================================================

def _is_local_request() -> bool:
    """Verifica se a requisição originou-se do próprio servidor."""
    return request.remote_addr in ("127.0.0.1", "::1")


def internal_only(f):
    """Decorator que restringe acesso a localhost."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not _is_local_request():
            abort(403)
        return f(*args, **kwargs)
    return decorated


@visitor_bp.route("/internal/stats", methods=["GET"])
@internal_only
def internal_stats():
    """[ROTA INTERNA] Estatísticas básicas do sistema."""
    from flask import jsonify

    total_visitors = db.session.query(Visitor).count()
    total_visits   = db.session.query(Visit).count()
    open_visits    = db.session.query(Visit).filter(Visit.check_out.is_(None)).count()
    with_photo     = db.session.query(Visitor).filter(Visitor.photo_data.isnot(None)).count()

    return jsonify({
        "total_visitors": total_visitors,
        "total_visits":   total_visits,
        "open_visits":    open_visits,
        "with_photo":     with_photo,
    })


@visitor_bp.route("/internal/health", methods=["GET"])
@internal_only
def internal_health():
    """[ROTA INTERNA] Health check."""
    from flask import jsonify
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})
