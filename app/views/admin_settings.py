# =====================================================================
# blueprints/admin_settings.py
# Blueprint de Configurações Administrativas — Responsável pela
# página de configurações do sistema e pela política de retenção de
# dados de visitantes (LGPD). Permite configurar prazo de retenção,
# ação a ser executada (exclusão ou anonimização), simulação de
# impacto e execução imediata do expurgo em lote.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, jsonify, redirect, render_template,
    request, url_for, current_app,
)
from sqlalchemy import and_, exists

from app.extensions import db
from app.models.settings import get_setting, set_setting
from app.models.visitor import Visitor, Visit

from app.utils.masking import (
    mask_name_first_plus_initials,
    mask_mom_name_keep_first,
    mask_phone_last4,
    mask_email_2first_2last_before_at,
)


# ─────────────────────────────────────────────────────────────────────
# Blueprint — Registro
# ─────────────────────────────────────────────────────────────────────

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# =====================================================================
# Funções Auxiliares — Snapshot de Configurações
# =====================================================================

def _settings_snapshot() -> dict:
    """
    Carrega as configurações de retenção atuais do banco (tabela
    settings) e retorna um dicionário normalizado com valores seguros.

    Chaves retornadas:
    - retention_days (int):            Dias de retenção (0–999, 0 = desativado).
    - retention_action (str):          'delete' ou 'anonymize'.
    - anonymize_delete_photo (bool):   Se True, remove a foto ao anonimizar.

    :return: (dict) Snapshot das configurações de retenção.
    """
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


# =====================================================================
# Funções Auxiliares — Query de Visitantes Elegíveis para Retenção
# =====================================================================

def _eligible_visitors_query(retention_days: int):
    """
    Constrói a query de visitantes elegíveis para o expurgo por
    retenção de dados. Um visitante é elegível quando:

    1. retention_days >= 1 (política ativa).
    2. Visitor.last_checkout_at <= (agora UTC − retention_days).
    3. NÃO existe Visit aberta (checkout_at IS NULL) para o visitante.

    Se retention_days <= 0, retorna query vazia (1=0).

    :param retention_days: (int) Prazo de retenção em dias.
    :return: (Query) Query SQLAlchemy de Visitor filtrada.
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


# =====================================================================
# Funções Auxiliares — Manipulação de Foto no Disco
# =====================================================================

def _delete_photo_if_exists(visitor: Visitor) -> None:
    """
    Remove o arquivo físico da foto do visitante do disco, se existir.
    Falhas de I/O são logadas mas não interrompem o fluxo.

    :param visitor: (Visitor) Instância do visitante cuja foto será removida.
    """
    if not visitor.photo_rel_path:
        return

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        return

    abs_path = os.path.join(upload_folder, visitor.photo_rel_path)
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception:
        current_app.logger.exception("Falha ao remover foto: %s", abs_path)


# =====================================================================
# Funções Auxiliares — Anonimização de Visitante
# =====================================================================

def _anonymize_visitor(v, delete_photo: bool) -> None:
    """
    Aplica máscaras de anonimização nos campos sensíveis do visitante,
    utilizando as funções do módulo masking.py:

    - name:           Primeiro nome + iniciais dos sobrenomes.
    - mom_name:       Apenas o primeiro nome.
    - phone:          Somente os últimos 4 dígitos visíveis.
    - email:          2 primeiros + 2 últimos caracteres antes do @.
    - photo_rel_path: Removida do disco e limpa (se delete_photo=True).

    :param v:            (Visitor) Instância do visitante a anonimizar.
    :param delete_photo: (bool) Se True, remove a foto física e limpa o caminho.
    """
    v.name = mask_name_first_plus_initials(v.name)
    v.mom_name = mask_mom_name_keep_first(v.mom_name)
    v.phone = mask_phone_last4(v.phone)
    v.email = mask_email_2first_2last_before_at(v.email)

    if delete_photo:
        _delete_photo_if_exists(v)
        # Usa "" se a coluna for NOT NULL; usar None se for nullable
        v.photo_rel_path = ""


# =====================================================================
# Funções de Negócio — Simulação e Execução de Retenção
# =====================================================================

def retention_simulate(retention_days: int) -> int:
    """
    Conta quantos visitantes seriam afetados pela política de retenção
    com o prazo informado, sem executar nenhuma ação destrutiva.

    :param retention_days: (int) Prazo de retenção em dias.
    :return: (int) Quantidade de visitantes elegíveis.
    """
    q = _eligible_visitors_query(retention_days)
    return q.count()


def retention_run(retention_days: int, action: str, anonymize_delete_photo: bool) -> int:
    """
    Executa o expurgo de dados de visitantes elegíveis conforme a
    política de retenção. Processa em lotes de 200 registros para
    evitar estouro de memória e locks prolongados.

    Ações suportadas:
    - 'delete':    Remove visitante, visitas associadas e foto do disco.
    - 'anonymize': Aplica máscaras nos campos sensíveis (e opcionalmente
                   remove a foto).

    :param retention_days:         (int)  Prazo de retenção em dias.
    :param action:                 (str)  Ação a executar ('delete' ou 'anonymize').
    :param anonymize_delete_photo: (bool) Se True, remove foto ao anonimizar.
    :return: (int) Quantidade de visitantes processados.
    :raises ValueError: Se a ação informada não for 'delete' nem 'anonymize'.
    """
    affected = 0
    batch_size = 200
    last_id = 0

    while True:
        batch = (
            _eligible_visitors_query(retention_days)
            .filter(Visitor.id > last_id)
            .order_by(Visitor.id.asc())
            .limit(batch_size)
            .all()
        )
        if not batch:
            break

        for v in batch:
            last_id = v.id

            if action == "delete":
                _delete_photo_if_exists(v)
                Visit.query.filter(Visit.visitor_id == v.id).delete(synchronize_session=False)
                db.session.delete(v)
                affected += 1

            elif action == "anonymize":
                _anonymize_visitor(v, delete_photo=anonymize_delete_photo)
                affected += 1
            else:
                raise ValueError("action inválida")

        db.session.commit()

    return affected


# =====================================================================
# Rotas — Página de Configurações (GET / POST)
# =====================================================================

@admin_bp.get("/settings")
def settings_page():
    """
    GET /admin/settings
    Renderiza a página de configurações administrativas com os
    valores atuais de retenção carregados do banco.
    """
    s = _settings_snapshot()
    return render_template("admin/settings.html", settings=s)


@admin_bp.post("/settings")
def settings_post():
    """
    POST /admin/settings
    Recebe o formulário de configurações, valida/normaliza os campos
    de retenção e persiste no banco via set_setting(). Redireciona
    de volta para a página de configurações após salvar.

    Campos esperados (form-data):
    - retention_days (str):            Dias de retenção (0–999).
    - retention_action (str):          'delete' ou 'anonymize'.
    - anonymize_delete_photo (str):    '1' para remover foto ao anonimizar.
    """
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


# =====================================================================
# Rotas — API de Retenção (Simulação e Execução)
# =====================================================================

@admin_bp.post("/settings/retention/simulate")
def settings_retention_simulate():
    """
    POST /admin/settings/retention/simulate
    Endpoint JSON que retorna a contagem de visitantes que seriam
    afetados pela política de retenção com o prazo informado.

    Payload JSON esperado:
    - retention_days (int): Prazo de retenção em dias.

    Resposta JSON:
    - count (int): Quantidade de visitantes elegíveis.
    """
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
    """
    POST /admin/settings/retention/run-now
    Endpoint JSON que executa imediatamente o expurgo de dados
    conforme a política de retenção informada no payload.

    Payload JSON esperado:
    - retention_days (int):            Prazo de retenção em dias.
    - action (str):                    'delete' ou 'anonymize'.
    - anonymize_delete_photo (bool):   Se True, remove foto ao anonimizar.

    Resposta JSON:
    - affected (int): Quantidade de visitantes processados.

    Erros:
    - 400: Se a ação informada for inválida.
    """
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
