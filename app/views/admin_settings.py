# =====================================================================
# views/admin_settings.py
# Blueprint de Configurações Administrativas do SISPORT
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from flask import (
    Blueprint, current_app, flash, redirect, render_template,
    request, send_file, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.settings import get_setting, set_setting
from app.models.visitor import Visitor, Visit
from app.defaults import build_snapshot
# ✅ IMPORT LIMPO no admin_settings.py
from app.paths import (
    BACKUP_DIR,
    UPLOADS_DIR,
    EXPORTS_DIR,
    IMPORTS_DIR,
)


# ─────────────────────────────────────────────────────────────────────
# Blueprint
# ─────────────────────────────────────────────────────────────────────
admin_bp = Blueprint("admin", __name__)


# ─────────────────────────────────────────────────────────────────────
# Chaves exportáveis (senha NUNCA é exportada)
# ─────────────────────────────────────────────────────────────────────
_EXPORTABLE_KEYS = [
    "retention_days",
    "retention_action",
    "retention_anonymize_delete_photo",
    "inst_name",
    "inst_short_name",
    "header_line_1",
    "header_line_2",
    "visitor_categories",
]


# =====================================================================
# Snapshot — Carrega todas as configurações para o template
# =====================================================================

def _settings_snapshot() -> dict:
    """Retorna TODAS as configurações — gerado automaticamente do DEFAULTS."""
    return build_snapshot(get_setting)

# =====================================================================
# Resetar configurações — Volta todas as configurações para o padrão
# =====================================================================

# =========== Reseta todas as cofigurações ============================
@admin_bp.post("/settings/reset-defaults")
def reset_defaults():
    """Restaura TODAS as configurações para os valores padrão."""
    from app.defaults import DEFAULTS
    from app.models.settings import set_setting

    # Senha administrativa NUNCA é resetada por segurança
    PROTECTED_KEYS = {"admin_password_hash"}

    restored = 0
    for key, (default_value, _type) in DEFAULTS.items():
        if key not in PROTECTED_KEYS:
            set_setting(key, default_value)
            restored += 1

    db.session.commit()
    flash(f"Configurações restauradas ao padrão ({restored} parâmetros).", "success")
    return redirect(url_for("admin.settings_page", tab_key="general"))

# =========== Reseta apenas as abas e seções ============================
@admin_bp.post("/settings/reset-defaults/<tab_key>")
def reset_tab_defaults(tab_key: str):
    """Restaura apenas as configs de uma aba específica."""
    from app.defaults import DEFAULTS

    # Mapeia aba → prefixos das chaves
    TAB_PREFIXES = {
        "general":  ("inst_", "header_"),
        "visitors": ("visitor_",),
        "database": ("retention_",),
    }

    prefixes = TAB_PREFIXES.get(tab_key)
    if not prefixes:
        flash("Aba não reconhecida.", "warning")
        return redirect(url_for("admin.settings_page", tab_key=tab_key))

    restored = 0
    for key, (default_value, _type) in DEFAULTS.items():
        if any(key.startswith(p) for p in prefixes):
            set_setting(key, default_value)
            restored += 1

    db.session.commit()
    flash(f"{restored} configurações desta aba restauradas ao padrão.", "success")
    return redirect(url_for("admin.settings_page", tab_key=tab_key))



# =====================================================================
# Rota — Página de Configurações (GET)
# =====================================================================

@admin_bp.get("/settings")
@admin_bp.get("/settings/<tab_key>")
def settings_page(tab_key: str = "general"):
    """Renderiza a página de configurações com a aba selecionada."""
    from app.controllers.config_registry import SETTINGS_TABS

    settings = _settings_snapshot()

    # Resolve o dict da aba ativa a partir da key
    current_tab = None
    for tab in SETTINGS_TABS:
        if tab["key"] == tab_key:
            current_tab = tab
            break

    # Fallback: se a key não existir, usa a primeira aba
    if current_tab is None:
        current_tab = SETTINGS_TABS[0]
        tab_key = current_tab["key"]

    return render_template(
        "admin/settings_page.html",
        tabs=SETTINGS_TABS,
        active_tab=tab_key,
        current_tab=current_tab,
        settings=settings,
    )



# =====================================================================
# Rotas — Salvar Geral (Instituição)
# =====================================================================

@admin_bp.post("/settings/general")
def save_general():
    """Salva dados da instituição."""
    for key in ("inst_name", "inst_short_name", "header_line_1", "header_line_2"):
        set_setting(key, request.form.get(key, "").strip())
    db.session.commit()
    flash("Dados da instituição salvos.", "success")
    return redirect(url_for("admin.settings_page", tab_key="general"))


# =====================================================================
# Rotas — Alterar Senha Administrativa
# =====================================================================

@admin_bp.post("/settings/change-password")
def change_password():
    """Cria ou altera a senha administrativa."""
    current = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    stored_hash = get_setting("admin_password_hash", "")

    # Se já tem senha, exige a atual
    if stored_hash and not check_password_hash(stored_hash, current):
        flash("Senha atual incorreta.", "danger")
        return redirect(url_for("admin.settings_page", tab_key="security"))

    if len(new_pwd) < 4:
        flash("A nova senha deve ter pelo menos 4 caracteres.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="security"))

    if new_pwd != confirm:
        flash("As senhas não coincidem.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="security"))

    set_setting("admin_password_hash", generate_password_hash(new_pwd))
    db.session.commit()

    action = "alterada" if stored_hash else "definida"
    flash(f"Senha administrativa {action} com sucesso.", "success")
    return redirect(url_for("admin.settings_page", tab_key="security"))


# =====================================================================
# Rotas — Salvar Configurações de Visitantes
# =====================================================================

@admin_bp.post("/settings/visitors")
def save_visitors():
    """Salva categorias de visitante e campos obrigatórios."""

    # ── Categorias ────────────────────────────────────────────────
    raw = request.form.get("visitor_categories", "") or request.form.get("categories_list", "")
    cats = [c.strip().lower() for c in raw.replace("\n", ",").split(",") if c.strip()]
    set_setting("visitor_categories", ",".join(cats) if cats else "civil")

    # ── Campos obrigatórios ───────────────────────────────────────
    set_setting("visitor_father_name_required", "1" if request.form.get("father_name_required") else "0")
    set_setting("visitor_email_required",       "1" if request.form.get("email_required") else "0")
    set_setting("visitor_empresa_required",     "1" if request.form.get("empresa_required") else "0")

    db.session.commit()
    flash("Configurações de visitantes salvas.", "success")
    return redirect(url_for("admin.settings_page", tab_key="visitors"))


# =====================================================================
# Rotas — Salvar Retenção de Dados
# =====================================================================

@admin_bp.post("/settings/database")
def save_database():
    """Salva configurações de retenção de dados."""
    days = request.form.get("retention_days", "0")
    action = request.form.get("retention_action", "delete")
    anon_photo = "1" if request.form.get("anonymize_delete_photo") else "0"

    try:
        days_int = max(0, min(999, int(days)))
    except (ValueError, TypeError):
        days_int = 0

    set_setting("retention_days", str(days_int))
    set_setting("retention_action", action if action in ("delete", "anonymize") else "delete")
    set_setting("retention_anonymize_delete_photo", anon_photo)
    db.session.commit()

    flash("Configurações de retenção salvas.", "success")
    return redirect(url_for("admin.settings_page", tab_key="database"))


# =====================================================================
# Rotas — Simulação de Retenção
# =====================================================================

@admin_bp.post("/settings/retention/simulate")
def settings_retention_simulate():
    """Conta quantos visitantes seriam afetados pela limpeza."""
    from flask import jsonify

    data = request.get_json(silent=True) or {}
    days = int(data.get("retention_days", 0))

    if days <= 0:
        return jsonify({"count": 0})

    cutoff = datetime.now(timezone.utc).replace(
        tzinfo=None
    ) - __import__("datetime").timedelta(days=days)

    count = Visitor.query.filter(
        Visitor.last_checkout_at.isnot(None),
        Visitor.last_checkout_at < cutoff,
    ).count()

    return jsonify({"count": count})


# =====================================================================
# Rotas — Executar Retenção Agora
# =====================================================================

@admin_bp.post("/settings/retention/run-now")
def settings_retention_run_now():
    """Executa limpeza de retenção imediatamente."""
    from flask import jsonify
    from datetime import timedelta

    data = request.get_json(silent=True) or {}
    days = int(data.get("retention_days", 0))
    action = data.get("action", "delete")
    del_photo = bool(data.get("anonymize_delete_photo", 0))

    if days <= 0:
        return jsonify({"affected": 0})

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    visitors = Visitor.query.filter(
        Visitor.last_checkout_at.isnot(None),
        Visitor.last_checkout_at < cutoff,
    ).all()

    affected = 0

    for v in visitors:
        if action == "delete":
            # Apaga foto do disco
            if v.photo_rel_path:
                photo_full = UPLOADS_DIR / v.photo_rel_path
                if photo_full.is_file():
                    photo_full.unlink(missing_ok=True)
            # Apaga visitas e visitante
            Visit.query.filter_by(visitor_id=v.id).delete()
            db.session.delete(v)
        else:
            # Anonimizar
            v.name = "ANONIMIZADO"
            v.doc_number = f"ANON-{v.id}"
            v.mom_name = ""
            v.phone = ""
            v.email = ""
            if del_photo and v.photo_rel_path:
                photo_full = UPLOADS_DIR / v.photo_rel_path
                if photo_full.is_file():
                    photo_full.unlink(missing_ok=True)
                v.photo_rel_path = ""
        affected += 1

    db.session.commit()
    return jsonify({"affected": affected})


# =====================================================================
# Rotas — Backup do Banco de Dados
# =====================================================================

@admin_bp.post("/settings/backup")
def create_backup():
    """Cria backup do banco SQLite e retorna para download."""
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")

    if "sqlite" not in db_uri:
        flash("Backup só é suportado para bancos SQLite.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    db_file = db_uri.replace("sqlite:///", "")
    if not os.path.isfile(db_file):
        flash("Arquivo do banco não encontrado.", "danger")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"sisport_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name

    shutil.copy2(db_file, str(backup_path))

    return send_file(
        str(backup_path),
        as_attachment=True,
        download_name=backup_name,
        mimetype="application/x-sqlite3",
    )


# =====================================================================
# Rotas — Exportar Configurações (JSON)
# =====================================================================

@admin_bp.get("/settings/export")
def export_settings():
    """Exporta configurações (exceto senha) como arquivo JSON."""
    data = {}
    for key in _EXPORTABLE_KEYS:
        data[key] = get_setting(key, "")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sisport_config_{timestamp}.json"
    file_path = EXPORTS_DIR / filename

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    file_path.write_text(json_str, encoding="utf-8")

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=filename,
        mimetype="application/json",
    )


# =====================================================================
# Rotas — Importar Configurações (JSON)
# =====================================================================

@admin_bp.post("/settings/import")
def import_settings():
    """Importa configurações de um arquivo JSON enviado pelo usuário."""
    file = request.files.get("config_file")

    if not file or not file.filename:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    if not file.filename.endswith(".json"):
        flash("O arquivo deve ser .json.", "danger")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    try:
        # Salva cópia local
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = IMPORTS_DIR / f"imported_config_{timestamp}.json"
        file.save(str(saved_path))

        data = json.loads(saved_path.read_text(encoding="utf-8"))

        if not isinstance(data, dict):
            raise ValueError("O arquivo deve conter um objeto JSON válido.")

        imported = 0
        for key in _EXPORTABLE_KEYS:
            if key in data:
                set_setting(key, str(data[key]))
                imported += 1

        db.session.commit()
        flash(f"Configurações importadas ({imported} parâmetros).", "success")

    except json.JSONDecodeError:
        flash("Arquivo JSON inválido.", "danger")
    except Exception as e:
        flash(f"Erro ao importar: {e}", "danger")

    return redirect(url_for("admin.settings_page", tab_key="database"))


# =====================================================================
# Rotas — Exportar Visitantes e Visitas (JSON)
# =====================================================================

@admin_bp.get("/settings/export-visitors")
def export_visitors():
    """Exporta todos os visitantes e suas visitas como JSON."""
    visitors = Visitor.query.order_by(Visitor.id.asc()).all()

    records = []
    for v in visitors:
        visits_data = []
        for vis in Visit.query.filter_by(visitor_id=v.id).order_by(Visit.id.asc()).all():
            visits_data.append({
                "destination": vis.destination,
                "reason":       vis.reason,
                "badge_number": vis.badge_number,
                "check_in":     vis.check_in.isoformat() if vis.check_in else None,
                "check_out":    vis.check_out.isoformat() if vis.check_out else None,
            })

        records.append({
            "name":            v.name,
            "doc_type":        v.doc_type,
            "doc_number":      v.doc_number,
            "mom_name":        v.mom_name,
            "phone":           v.phone,
            "email":           v.email,
            "category":        v.category,
            "photo_rel_path":  v.photo_rel_path,
            "last_checkout_at": v.last_checkout_at.isoformat() if v.last_checkout_at else None,
            "visits":          visits_data,
        })

    export_data = {
        "exported_at":     datetime.now(timezone.utc).isoformat(),
        "total_visitors":  len(records),
        "total_visits":    sum(len(r["visits"]) for r in records),
        "visitors":        records,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sisport_visitors_{timestamp}.json"
    file_path = EXPORTS_DIR / filename

    json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
    file_path.write_text(json_str, encoding="utf-8")

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=filename,
        mimetype="application/json",
    )


# =====================================================================
# Rotas — Importar Visitantes (JSON)
# =====================================================================

@admin_bp.post("/settings/import-visitors")
def import_visitors():
    """
    Importa visitantes e visitas de um arquivo JSON.
    Duplicatas (mesmo doc_type + doc_number) são ignoradas.
    """
    file = request.files.get("visitors_file")

    if not file or not file.filename:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    if not file.filename.endswith(".json"):
        flash("O arquivo deve ser .json.", "danger")
        return redirect(url_for("admin.settings_page", tab_key="database"))

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = IMPORTS_DIR / f"imported_visitors_{timestamp}.json"
        file.save(str(saved_path))

        data = json.loads(saved_path.read_text(encoding="utf-8"))

        if not isinstance(data, dict) or "visitors" not in data:
            raise ValueError("Formato inválido. Esperado JSON com chave 'visitors'.")

        created = 0
        skipped = 0

        for record in data["visitors"]:
            doc_type   = record.get("doc_type", "").strip()
            doc_number = record.get("doc_number", "").strip()

            if not doc_number:
                skipped += 1
                continue

            existing = Visitor.query.filter_by(
                doc_type=doc_type,
                doc_number=doc_number,
            ).first()

            if existing:
                skipped += 1
                continue

            v = Visitor(
                name=record.get("name", ""),
                doc_type=doc_type,
                doc_number=doc_number,
                mom_name=record.get("mom_name", ""),
                phone=record.get("phone", ""),
                email=record.get("email", ""),
                category=record.get("category", "civil"),
                photo_rel_path=record.get("photo_rel_path", ""),
            )

            lc = record.get("last_checkout_at")
            if lc:
                try:
                    v.last_checkout_at = datetime.fromisoformat(lc)
                except (ValueError, TypeError):
                    v.last_checkout_at = None

            db.session.add(v)
            db.session.flush()

            for vis_data in record.get("visits", []):
                check_in = check_out = None
                try:
                    ci = vis_data.get("check_in")
                    if ci:
                        check_in = datetime.fromisoformat(ci)
                    co = vis_data.get("check_out")
                    if co:
                        check_out = datetime.fromisoformat(co)
                except (ValueError, TypeError):
                    pass

                visit = Visit(
                    visitor_id=v.id,
                    destination=vis_data.get("destination", ""),
                    reason=vis_data.get("reason", ""),
                    badge_number=vis_data.get("badge_number", ""),
                    check_in=check_in,
                    check_out=check_out,
                )
                db.session.add(visit)

            created += 1

        db.session.commit()
        flash(
            f"Importação concluída: {created} visitantes criados, "
            f"{skipped} ignorados (duplicatas ou sem documento).",
            "success",
        )

    except json.JSONDecodeError:
        flash("Arquivo JSON inválido.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao importar: {e}", "danger")

    return redirect(url_for("admin.settings_page", tab_key="database"))
