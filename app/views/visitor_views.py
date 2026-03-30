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
from ..utils.validators import validate_required_email
from sqlalchemy.exc import IntegrityError

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
    visitor_photo_update
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

    :return: Template 'identify.html'.
    """
    return render_template("identify.html")


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
    para a listagem de visitas abertas.

    :param visit_id: (int) ID da visita na URL.
    :return: Redirect para open_visits.
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
            form['cpf'], form['phone'], form['email'], form['empresa'].
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


@visitor_bp.route("/wizard/finish", methods=["POST"])
def wizard_finish():
    """
    Etapa final do wizard: cria o visitante no banco (se não existir)
    e registra a primeira entrada (check-in). Limpa a sessão do wizard.

    :input: form['destination'] — Local/destino da visita.
    :return: Redirect para identify com mensagem de sucesso ou erro.
    """
    try:
        visitor = create_visitor_if_not_exists_from_wizard()
        destination = request.form.get("destination", "")
        visit_id = register_checkin(visitor, destination)
        flash(f"Cadastro criado e entrada registrada (visita {visit_id}).", "success")
        session.pop("wizard", None)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.identify"))


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
# Rotas — Listagens e Relatórios
# =====================================================================

@visitor_bp.route("/open", methods=["GET"])
def open_visits():
    """
    Lista todas as visitas em aberto (sem check-out registrado),
    ordenadas pela entrada mais recente. Permite dar baixa (check-out).

    :return: Template 'report_day.html' com visitas abertas e botão de checkout.
    """
    open_list = (
        db.session.query(Visit)
        .filter(Visit.check_out.is_(None))
        .order_by(Visit.check_in.desc())
        .all()
    )
    return render_template(
        "report_day.html",
        visits=open_list,
        title="Visitas em aberto",
        show_checkout=True,
    )


@visitor_bp.route("/report/today", methods=["GET"])
def report_today():
    """
    Exibe o relatório do dia atual com todas as visitas registradas,
    utilizando o controller de relatórios.

    :return: Template 'report_day.html' com visitas do dia (sem botão de checkout).
    """
    visits = day_report(date.today())
    return render_template(
        "report_day.html",
        visits=visits,
        title="Relatório de Hoje",
        show_checkout=False,
    )

@visitor_bp.route("/report/today/print")
def report_today_print():
    """
    Gera uma versão para impressão do relatório do dia atual,
    com todas as visitas e horário de geração.

    :return: Template 'print_day.html' com visitas do dia e timestamp de geração.
    """
    today = date.today()
    visits = db.session.query(Visit).filter(
        db.func.date(Visit.check_in) == today
    ).order_by(Visit.check_in.desc()).all()
    
    generated_at = datetime.now()
    return render_template('print_day.html', visits=visits, today=today, generated_at=generated_at)


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
    obrigatórios (nome, telefone, nome da mãe, e-mail) e persiste
    as alterações no banco. Trata conflito de e-mail duplicado.

    :param visitor_id: (int) ID do visitante na URL.
    :input: form['name'], form['phone'], form['mom_name'],
            form['father_name'], form['empresa'], form['email'].
    :return: Redirect para visitor_edit com mensagem de sucesso ou erro.
    """
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    mom_name = (request.form.get("mom_name") or "").strip()
    father_name = (request.form.get("father_name") or "").strip()
    empresa = (request.form.get("empresa") or "").strip()

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

    v.name = name
    v.phone = phone
    v.email = email
    v.mom_name = mom_name
    v.father_name = father_name or None
    v.empresa = empresa or None

    try:
        db.session.commit()
        flash("Cadastro atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao salvar: este e-mail já está cadastrado para outro visitante.", "danger")

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
