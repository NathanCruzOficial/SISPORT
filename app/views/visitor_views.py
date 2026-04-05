# =====================================================================
# visitor_views.py
# Views (Rotas) de Visitantes — Define todas as rotas do Blueprint
# de visitantes, incluindo: identificação por CPF, wizard de cadastro
# (3 etapas), check-in/check-out, servimento de uploads, relatórios
# diários, edição/exclusão de visitantes e atualização de foto.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import os
from datetime import date, datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    abort,
    send_from_directory,
)
from werkzeug.utils import safe_join

from ..extensions import db
from ..models.visitor import Visitor, Visit
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
from ..controllers.report_controller import day_report
from ..utils.validators import normalize_cpf, is_valid_cpf, validate_required_email
from sqlalchemy.exc import IntegrityError


# ─────────────────────────────────────────────────────────────────────
# Variáveis Globais — Blueprint
# ─────────────────────────────────────────────────────────────────────

# Blueprint principal de visitantes, registrado sem prefixo de URL.
visitor_bp = Blueprint("visitor", __name__)


# =====================================================================
# Rotas — Identificação por CPF (Tela Inicial)
# =====================================================================

@visitor_bp.route("/", methods=["GET"])
def identify():
    """
    Renderiza a tela inicial de identificação por CPF.
    Inclui dados de status geral e lista de visitas em aberto.
    """
    from datetime import date

    # Visitas em aberto (sem check-out)
    open_list = (
        db.session.query(Visit)
        .filter(Visit.check_out.is_(None))
        .order_by(Visit.check_in.desc())
        .all()
    )

    # Contagem de visitas do dia
    today = date.today()
    today_visits = (
        db.session.query(Visit)
        .filter(db.func.date(Visit.check_in) == today)
        .all()
    )

    # Saídas registradas hoje
    checked_out_today = sum(1 for v in today_visits if v.check_out is not None)

    # Total de visitantes cadastrados
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
    Valida o CPF informado; se o visitante já existe, redireciona para
    o check-in. Caso contrário, inicializa o wizard de novo cadastro.

    :input: form['cpf'] — CPF digitado pelo usuário.
    :return: Redirect para checkin_form (existente) ou wizard (novo).
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
    Exibe a ficha do visitante já cadastrado (GET) e registra uma nova
    entrada/check-in (POST) com o destino informado.

    :param visitor_id: (int) ID do visitante na URL.
    :input: form['destination'] — Local/destino da visita (POST).
    :return: Template 'checkin_existing.html' (GET) ou redirect para identify (POST).
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
    Registra a saída (check-out) de uma visita em aberto e redireciona
    de volta para a listagem de visitas abertas.
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
    Inicializa a sessão do wizard caso ainda não exista.

    :return: Template 'visitor_wizard.html' com dados do wizard na sessão.
    """
    if "wizard" not in session:
        wizard_start_for_new_visitor()
    return render_template("visitor_wizard.html", wizard=session["wizard"])


@visitor_bp.route("/wizard/step1", methods=["POST"])
def wizard_step1():
    """
    Processa o formulário da Etapa 1 do wizard (dados pessoais).
    Delega a validação e persistência em sessão ao controller.

    :input: form['name'], form['father_name'], form['mom_name'],
            form['cpf'], form['phone'], form['email'], form['empresa'], form['category'].
    :return: Redirect para wizard (avança para etapa 2 ou exibe erro).
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
            request.form.get("category", "civil"),    # ← NOVO
        )
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/step2", methods=["POST"])
def wizard_step2():
    """
    Processa a Etapa 2 do wizard: captura e salvamento da foto
    vinculada ao CPF. Permite pular (skip) sem foto.

    :input: form['skip'] — Se presente, pula a captura de foto.
            form['photo_data_url'] — Foto em data URL base64 (opcional).
    :return: Redirect para wizard (avança para etapa 3 ou exibe erro).
    """
    skip = request.form.get("skip")
    photo_data_url = None if skip else (request.form.get("photo_data_url") or "")
    try:
        wizard_step2_submit(photo_data_url)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.wizard"))


# ── NOVO: Navegar para trás entre etapas ──────────────────────────
@visitor_bp.route("/wizard/back/<int:step>", methods=["GET"])
def wizard_back(step: int):
    """Volta o wizard para a etapa indicada (1 ou 2), sem perder dados."""
    w = session.get("wizard")
    if not w:
        return redirect(url_for("visitor.identify"))

    # Só permite voltar para etapa anterior à atual
    target = max(1, min(step, w.get("step", 1)))
    w["step"] = target
    session["wizard"] = w
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/finish", methods=["POST"])
def wizard_finish():
    """
    Etapa final do wizard: cria o visitante no banco (se não existir)
    e registra a primeira entrada (check-in). Limpa a sessão do wizard.
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

    except Exception as e:                    # ← MUDOU: era ValueError
        flash(str(e), "danger")
        return redirect(url_for("visitor.wizard"))


# =====================================================================
# Rotas — Servimento de Arquivos (Uploads / Fotos)
# =====================================================================

@visitor_bp.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename):
    """
    Serve arquivos de upload (fotos de visitantes). Se o arquivo não
    existir no disco, retorna uma imagem placeholder padrão.

    :param filename: (str) Caminho relativo do arquivo dentro de UPLOAD_FOLDER.
    :return: Arquivo solicitado ou 'avatar-placeholder.jpg' como fallback.
    """
    base = current_app.config["UPLOAD_FOLDER"]
    full = safe_join(base, filename)

    # se não existir, devolve placeholder
    if not full or not os.path.isfile(full):
        return send_from_directory(
            os.path.join(current_app.root_path, "static", "img"),
            "avatar-placeholder.jpg",
        )

    return send_from_directory(base, filename)



# =====================================================================
# Rotas — Visitas em Aberto (Controle em tempo real)
# =====================================================================

@visitor_bp.route("/open", methods=["GET"])
def open_visits():
    """
    Lista todas as visitas em aberto (sem check-out) com controle
    de saída e edição. Página dedicada ao monitoramento em tempo real.
    """
    # Visitas em aberto
    open_list = (
        db.session.query(Visit)
        .filter(Visit.check_out.is_(None))
        .order_by(Visit.check_in.asc())  # mais antiga primeiro
        .all()
    )

    # Contagens do dia para os cards de resumo
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
    """
    Relatório unificado com filtros de período, busca por nome/CPF,
    status (abertos/finalizados/todos) e destino.
    Parâmetros via query string para permitir bookmarks e compartilhamento.
    """
    from datetime import timedelta

    # ── Parâmetros de filtro ──────────────────────────────────────────
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    search    = request.args.get("search", "").strip()
    status    = request.args.get("status", "all")       # all | open | closed
    category  = request.args.get("category", "all")     # all | civil | militar | ex-militar

    
    # Defaults: se nenhuma data informada, usa hoje
    today = date.today()
    try:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today
    except ValueError:
        dt_from = today
    try:
        dt_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    except ValueError:
        dt_to = today

    # Garante que dt_from <= dt_to
    if dt_from > dt_to:
        dt_from, dt_to = dt_to, dt_from

    # ── Query base ────────────────────────────────────────────────────
    query = (
        db.session.query(Visit)
        .join(Visitor, Visit.visitor_id == Visitor.id)
        .filter(db.func.date(Visit.check_in) >= dt_from)
        .filter(db.func.date(Visit.check_in) <= dt_to)
    )

    # Filtro de status
    if status == "open":
        query = query.filter(Visit.check_out.is_(None))
    elif status == "closed":
        query = query.filter(Visit.check_out.isnot(None))

    # Filtro de categoria
    if category in ("civil", "militar", "ex-militar"):
        query = query.filter(Visitor.category == category)

    # Filtro de busca (nome, CPF ou destino)
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

    # ── Contadores para os badges ─────────────────────────────────────
    total    = len(visits)
    open_ct  = sum(1 for v in visits if v.check_out is None)
    closed_ct = total - open_ct

    # ── Título dinâmico ───────────────────────────────────────────────
    if dt_from == dt_to == today:
        title = "Relatório de Hoje"
    elif dt_from == dt_to:
        title = f"Relatório — {dt_from.strftime('%d/%m/%Y')}"
    else:
        title = f"Relatório — {dt_from.strftime('%d/%m/%Y')} a {dt_to.strftime('%d/%m/%Y')}"

    # ── Filtros ativos (para manter estado no template) ───────────────
    # Dentro de report_page(), onde monta o dict filters:
    filters = {
        "date_from":     dt_from.strftime("%Y-%m-%d"),
        "date_to":       dt_to.strftime("%Y-%m-%d"),
        "date_from_fmt": dt_from.strftime("%d/%m/%Y"),
        "date_to_fmt":   dt_to.strftime("%d/%m/%Y"),
        "search":        search,
        "status":        status,
        "category":      category,
    }


    return render_template(
        "report_page.html",
        visits=visits,
        title=title,
        filters=filters,
        total=total,
        open_count=open_ct,
        closed_count=closed_ct,
    )


@visitor_bp.route("/report/print", methods=["GET"])
def report_print():
    """
    Versão para impressão do relatório, usando os mesmos filtros
    da query string. Passa filtros formatados para exibição no documento.
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

    # ── Query com filtros ─────────────────────────────────────────
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

    # ── Contadores ────────────────────────────────────────────────
    open_count   = sum(1 for v in visits if v.check_out is None)
    closed_count = len(visits) - open_count

    # ── Filtros para o template (valores brutos + formatados) ─────
    filters = {
        "date_from":     dt_from.strftime("%Y-%m-%d"),
        "date_to":       dt_to.strftime("%Y-%m-%d"),
        "date_from_fmt": dt_from.strftime("%d/%m/%Y"),
        "date_to_fmt":   dt_to.strftime("%d/%m/%Y"),
        "search":        search,
        "status":        status,
        "category":      category,
    }

    return render_template(
        "print_day.html",
        visits=visits,
        today=today,
        generated_at=datetime.now(),
        filters=filters,
        open_count=open_count,
        closed_count=closed_count,
    )



@visitor_bp.route("/report/today", methods=["GET"])
def report_today():
    """Redireciona para o relatório unificado filtrado por hoje."""
    today = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("visitor.report_page", date_from=today, date_to=today))


@visitor_bp.route("/report/today/print")
def report_today_print():
    """Redireciona para impressão com filtro de hoje."""
    today = date.today().strftime("%Y-%m-%d")
    return redirect(url_for("visitor.report_print", date_from=today, date_to=today))




# =====================================================================
# Rotas — Edição de Visitantes
# =====================================================================

def _safe_unlink(abs_path: str) -> None:
    """
    Remove um arquivo do disco de forma segura, ignorando erros caso
    o arquivo não exista ou não possa ser removido.

    :param abs_path: (str) Caminho absoluto do arquivo a ser removido.
    :return: None.
    """
    try:
        if abs_path and os.path.exists(abs_path):
            os.remove(abs_path)
    except OSError:
        pass


@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["GET"])
def visitor_edit(visitor_id):
    """
    Exibe o formulário de edição de um visitante existente.

    :param visitor_id: (int) ID do visitante na URL.
    :return: Template 'visitor_edit.html' com os dados do visitante.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))
    return render_template("visitor_edit.html", visitor=v)

@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["POST"])
def visitor_edit_post(visitor_id):
    """
    Processa o formulário de edição de visitante. Valida campos
    obrigatórios, verifica duplicidade no banco (excluindo o próprio
    visitante) e persiste as alterações.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    name = (request.form.get("name") or "").strip().upper()
    phone = (request.form.get("phone") or "").strip()
    mom_name = (request.form.get("mom_name") or "").strip().upper()
    father_name = (request.form.get("father_name") or "").strip().upper()
    empresa = (request.form.get("empresa") or "").strip().upper()
    category = (request.form.get("category") or "civil").strip().lower()

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

    # ── Verificação de duplicidade (exclui o próprio visitante) ───
    try:
        _check_duplicate_fields(
            name=name,
            father_name=father_name,
            mom_name=mom_name,
            cpf=v.cpf,          # CPF não muda na edição
            phone=phone,
            email=email,
            exclude_id=v.id,    # ← ignora ele mesmo na busca
        )
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))

    v.name = name
    v.phone = phone
    v.email = email
    v.mom_name = mom_name
    v.father_name = father_name or None
    v.empresa = empresa or None
    v.category = category  

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
    Recebe uma foto em formato data URL (base64) e atualiza a foto de
    perfil do visitante. Pode ser chamada pela tela de edição ou wizard.

    :param visitor_id: (int) ID do visitante na URL.
    :input: form['photo_data_url'] — Foto em data URL base64.
    :return: Redirect para visitor_edit com mensagem de sucesso ou erro.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    try:
        photo_url = request.form.get("photo_data_url", "")
        print(f"Recebido photo_data_url: {photo_url[:30]}...")

        visitor_photo_update(v, photo_url)
        flash("Foto atualizada.", "success")

    except Exception as e:
        db.session.rollback()  # bom ter, caso algo dê errado depois do commit (ou em evoluções futuras)
        flash(str(e), "danger")

    return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))


# ─────────────────────────────────────────────────────────────────────
# Código legado comentado — versão anterior de visitor_update_photo
# que realizava o salvamento direto via save_or_replace_profile_photo
# sem delegar ao controller. Substituída pelo uso de
# visitor_photo_update do controller.
# ─────────────────────────────────────────────────────────────────────
'''
@visitor_bp.route("/visitors/<int:visitor_id>/photo", methods=["POST"])
def visitor_update_photo(visitor_id):
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    try:
        data_url = request.form.get("photo_data_url", "")  # padronize esse nome no HTML/JS
        print(f"Recebido photo_data_url: {data_url[:30]}...")

        rel_path = save_or_replace_profile_photo(data_url, v.cpf)
        v.photo_rel_path = rel_path
        db.session.commit()

        flash("Foto atualizada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")

    return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))
'''


# =====================================================================
# Rotas — Exclusão de Visitante
# =====================================================================

@visitor_bp.route("/visitors/<int:visitor_id>/delete", methods=["POST"])
def visitor_delete(visitor_id):
    """
    Exclui um visitante e todos os seus registros de visita associados.
    Remove também a foto do disco, se existir.

    :param visitor_id: (int) ID do visitante na URL.
    :return: Redirect para identify com mensagem de sucesso ou erro.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    # Se você tiver relacionamento Visit -> Visitor com FK,
    # o delete pode falhar se existirem visitas. Você pode:
    # - apagar as visitas primeiro, ou
    # - configurar cascade no model.
    # Aqui vai o modo explícito (ajuste o nome do model/coluna):
    Visit.query.filter_by(visitor_id=v.id).delete()

    # remove foto do disco
    if v.photo_rel_path:
        abs_path = os.path.join(current_app.root_path, "static", v.photo_rel_path)
        _safe_unlink(abs_path)

    db.session.delete(v)
    db.session.commit()

    flash("Cadastro excluído.", "success")
    return redirect(url_for("visitor.identify"))
