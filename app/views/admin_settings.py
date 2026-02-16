# blueprints/admin_settings.py
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, current_app
from sqlalchemy import and_, exists

from app.extensions import db
from app.models.settings import get_setting, set_setting
from app.models.visitor import Visitor, Visit

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _settings_snapshot() -> dict:
    retention_days = int(get_setting("retention_days", "0") or "0")
    retention_days = max(0, min(999, retention_days))

    retention_action = get_setting("retention_action", "delete") or "delete"
    if retention_action not in ("delete", "anonymize"):
        retention_action = "delete"

    anonymize_delete_photo = (get_setting("retention_anonymize_delete_photo", "1") or "1") == "1"

    return {
        "retention_days": retention_days,
        "retention_action": retention_action,
        "anonymize_delete_photo": anonymize_delete_photo,
    }


def _eligible_visitors_query(retention_days: int):
    """
    Elegível se:
    - retention_days >= 1
    - Visitor.last_checkout_at <= now - retention_days
    - NÃO existe Visit aberta (checkout_at IS NULL)
    """
    if retention_days <= 0:
        return Visitor.query.filter(db.text("1=0"))

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    open_visit_exists = (
        db.session.query(Visit.id)
        .filter(and_(Visit.visitor_id == Visitor.id, Visit.check_out.is_(None)))
        .exists()
    )

    q = (
        Visitor.query
        .filter(Visitor.last_checkout_at.isnot(None))
        .filter(Visitor.last_checkout_at <= cutoff)
        .filter(~open_visit_exists)
    )
    return q


def _delete_photo_if_exists(visitor: Visitor) -> None:
    if not visitor.photo_rel_path:
        return

    # Ajuste conforme seu projeto: aqui assumo que você guarda uploads em UPLOAD_FOLDER
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        return

    abs_path = os.path.join(upload_folder, visitor.photo_rel_path)
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception:
        current_app.logger.exception("Falha ao remover foto: %s", abs_path)


def _anonymize_visitor(visitor: Visitor, delete_photo: bool) -> None:
    # Mantém ID e registros; remove identificação
    visitor.name = "ANONIMIZADO"
    visitor.cpf = None
    visitor.mom_name = None
    visitor.father_name = None
    visitor.phone = None
    visitor.email = None

    if delete_photo:
        _delete_photo_if_exists(visitor)
        visitor.photo_rel_path = None


def retention_simulate(retention_days: int) -> int:
    q = _eligible_visitors_query(retention_days)
    return q.count()


def retention_run(retention_days: int, action: str, anonymize_delete_photo: bool) -> int:
    q = _eligible_visitors_query(retention_days)

    # Para evitar carregar tudo em memória em bases grandes, processe em lotes:
    affected = 0
    batch_size = 200

    while True:
        batch = q.limit(batch_size).all()
        if not batch:
            break

        if action == "delete":
            # delete: apaga visitas + visitante + foto
            for v in batch:
                _delete_photo_if_exists(v)
                Visit.query.filter(Visit.visitor_id == v.id).delete(synchronize_session=False)
                db.session.delete(v)
                affected += 1

        elif action == "anonymize":
            for v in batch:
                _anonymize_visitor(v, delete_photo=anonymize_delete_photo)
                affected += 1
        else:
            raise ValueError("action inválida")

        db.session.commit()

    return affected


@admin_bp.get("/settings")
def settings_page():
    s = _settings_snapshot()
    return render_template("admin/settings.html", settings=s)


@admin_bp.post("/settings")
def settings_post():
    # Retenção
    retention_days_raw = request.form.get("retention_days", "0").strip()
    try:
        retention_days = int(retention_days_raw)
    except ValueError:
        retention_days = 0
    retention_days = max(0, min(999, retention_days))

    retention_action = request.form.get("retention_action", "delete")
    if retention_action not in ("delete", "anonymize"):
        retention_action = "delete"

    anonymize_delete_photo = "1" if request.form.get("anonymize_delete_photo") == "1" else "0"

    set_setting("retention_days", str(retention_days))
    set_setting("retention_action", retention_action)
    set_setting("retention_anonymize_delete_photo", anonymize_delete_photo)

    db.session.commit()
    return redirect(url_for("admin.settings_page"))


@admin_bp.post("/settings/retention/simulate")
def settings_retention_simulate():
    payload = request.get_json(silent=True) or {}
    try:
        retention_days = int(payload.get("retention_days", 0))
    except (TypeError, ValueError):
        retention_days = 0
    retention_days = max(0, min(999, retention_days))

    count = retention_simulate(retention_days)
    return jsonify({"count": count})


@admin_bp.post("/settings/retention/run-now")
def settings_retention_run_now():
    payload = request.get_json(silent=True) or {}
    try:
        retention_days = int(payload.get("retention_days", 0))
    except (TypeError, ValueError):
        retention_days = 0
    retention_days = max(0, min(999, retention_days))

    action = payload.get("action", "delete")
    if action not in ("delete", "anonymize"):
        return jsonify({"error": "Ação inválida"}), 400

    anonymize_delete_photo = bool(payload.get("anonymize_delete_photo", 1))

    affected = retention_run(retention_days, action, anonymize_delete_photo)
    return jsonify({"affected": affected})
