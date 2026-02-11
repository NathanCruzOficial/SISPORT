import os
import re
from datetime import date
import base64

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
from ..utils.validators import normalize_cpf, is_valid_cpf
from sqlalchemy.exc import IntegrityError

visitor_bp = Blueprint("visitor", __name__)


@visitor_bp.route("/", methods=["GET"])
def identify():
    """Tela inicial: identificar por CPF e decidir fluxo (existente vs novo)."""
    return render_template("identify.html")


@visitor_bp.route("/identify", methods=["POST"])
def identify_post():
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


@visitor_bp.route("/checkin/<int:visitor_id>", methods=["GET", "POST"])
def checkin_form(visitor_id: int):
    """Para visitante já cadastrado: mostra ficha + registra entrada."""
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


@visitor_bp.route("/wizard", methods=["GET"])
def wizard():
    """Exibe wizard 3 etapas (somente para novo cadastro)."""
    if "wizard" not in session:
        wizard_start_for_new_visitor()
    return render_template("visitor_wizard.html", wizard=session["wizard"])


@visitor_bp.route("/wizard/step1", methods=["POST"])
def wizard_step1():
    """Etapa 1 do wizard: identificação (nome/cpf)."""
    wizard_step1_submit(request.form.get("name", ""), request.form.get("cpf", ""), request.form.get("phone", ""))

    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/step2", methods=["POST"])
def wizard_step2():
    """Etapa 2 do wizard: captura e salvamento da foto vinculada ao CPF."""
    try:
        wizard_step2_submit(request.form.get("photo_data_url", ""))
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.wizard"))


@visitor_bp.route("/wizard/finish", methods=["POST"])
def wizard_finish():
    """Etapa 3 do wizard: cria cadastro (se necessário) e registra entrada."""
    try:
        visitor = create_visitor_if_not_exists_from_wizard()
        destination = request.form.get("destination", "")
        visit_id = register_checkin(visitor, destination)
        flash(f"Cadastro criado e entrada registrada (visita {visit_id}).", "success")
        session.pop("wizard", None)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.identify"))


@visitor_bp.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename):
    """Serve fotos da pasta uploads/ para exibição na interface."""
    base = current_app.config["UPLOAD_FOLDER"]

    # safe_join evita path traversal (../../etc/passwd)
    full = safe_join(base, filename)
    if not full or not os.path.isfile(full):
        abort(404)

    return send_from_directory(base, filename)


# ---------------------------
# Listagens / Relatórios
# ---------------------------

@visitor_bp.route("/open", methods=["GET"])
def open_visits():
    """Lista visitas em aberto (sem saída) para dar baixa."""
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


@visitor_bp.route("/checkout/<int:visit_id>", methods=["POST"])
def checkout(visit_id: int):
    """Registra saída (check-out) de uma visita em aberto."""
    try:
        checkout_visit(visit_id)
        flash("Saída registrada.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("visitor.open_visits"))


@visitor_bp.route("/report/today", methods=["GET"])
def report_today():
    """Mostra relatório do dia atual (todas as visitas do dia)."""
    visits = day_report(date.today())
    return render_template(
        "report_day.html",
        visits=visits,
        title="Relatório de Hoje",
        show_checkout=False,
    )


@visitor_bp.route("/report/today/print", methods=["GET"])
def report_today_print():
    """Página do relatório do dia otimizada para impressão."""
    visits = day_report(date.today())
    return render_template("print_day.html", visits=visits, today=date.today())


# --------------------------------------------------------------
# EDIÇÃO DE VISITANTES
# --------------------------------------------------------------

def _safe_unlink(abs_path: str) -> None:
    try:
        if abs_path and os.path.exists(abs_path):
            os.remove(abs_path)
    except OSError:
        pass


@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["GET"])
def visitor_edit(visitor_id):
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))
    return render_template("visitor_edit.html", visitor=v)


@visitor_bp.route("/visitors/<int:visitor_id>/edit", methods=["POST"])
def visitor_edit_post(visitor_id):
    v = db.session.get(Visitor, visitor_id)
    if not v:
        flash("Visitante não encontrado.", "warning")
        return redirect(url_for("visitor.identify"))

    v.name = (request.form.get("name") or "").strip()
    v.phone = (request.form.get("phone") or "").strip()

    try:
        db.session.commit()
        flash("Cadastro atualizado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao salvar (verifique campos duplicados/inválidos).", "danger")

    return redirect(url_for("visitor.visitor_edit", visitor_id=v.id))

# -----------------------------------------------------------------------------------------
# ATUALIZAÇÃO DE FOTO (pode ser feita tanto pelo wizard quanto pela edição de visitante)
# -----------------------------------------------------------------------------------------

@visitor_bp.route("/visitors/<int:visitor_id>/photo", methods=["POST"])
def visitor_update_photo(visitor_id):
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


@visitor_bp.route("/visitors/<int:visitor_id>/delete", methods=["POST"])
def visitor_delete(visitor_id):
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