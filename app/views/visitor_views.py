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
from datetime import date, datetime

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
from ..utils.validators import normalize_cpf, is_valid_cpf, validate_required_email
from sqlalchemy.exc import IntegrityError


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
            destination = request.form.get("destination", "")
            visit_id = register_checkin(visitor, destination)
            flash(f"Entrada registrada (visita {visit_id}).", "success")
            return redirect(url_for("visitor.identify"))
        except Exception as e:
            flash(str(e), "danger")

    return render_template("checkin_existing.html", visitor=visitor)


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
    return render_template("visitor_wizard.html", wizard=session["wizard"])


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
        destination = request.form.get("destination", "").strip()

        if destination:
            register_checkin(visitor, destination)
            flash("Visitante cadastrado e check-in registrado!", "success")
        else:
            flash("Visitante cadastrado com sucesso!", "success")

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
