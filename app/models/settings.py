# app/models/settings.py
"""
Modelo e helpers para a tabela **settings** (configurações do sistema).
"""

import json

from app.extensions import db
from app.defaults import get_default


# ── Modelo ────────────────────────────────────────────────────────────

class Setting(db.Model):
    """Representa um par chave/valor de configuração persistido no banco."""

    __tablename__ = "settings"

    id    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")

    def __repr__(self) -> str:
        return f"<Setting {self.key!r}={self.value!r}>"


# ── Helpers internos ──────────────────────────────────────────────────

def _next_id() -> int:
    """
    Retorna o próximo ID disponível para inserção.
    """
    max_id = db.session.query(
        db.func.coalesce(db.func.max(Setting.id), 0)
    ).scalar()
    return max_id + 1


# ── API pública ───────────────────────────────────────────────────────

def get_setting(key: str, fallback: str | None = None) -> str:
    """
    Obtém o valor de uma configuração.
    """
    row = Setting.query.filter_by(key=key).first()
    if row is not None:
        return row.value
    if fallback is not None:
        return fallback
    return get_default(key)


def set_setting(key: str, value: str) -> None:
    """
    Define (ou atualiza) o valor de uma configuração.
    """
    row = Setting.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(Setting(id=_next_id(), key=key, value=value))


# ── Metadados visuais das categorias ──────────────────────────────────

_CATEGORY_META = {
    "civil": {
        "label": "Civil",
        "icon": "bi-person",
        "btn_class": "btn-outline-secondary",
        "badge_class": "bg-secondary",
    },
    "militar": {
        "label": "Militar",
        "icon": "bi-shield-fill",
        "btn_class": "btn-outline-success",
        "badge_class": "bg-success",
    },
    "prestador": {
        "label": "Prestador",
        "icon": "bi-tools",
        "btn_class": "btn-outline-primary",
        "badge_class": "bg-primary",
    },
}


def _parse_categories_raw(raw: str) -> list[str]:
    """
    Faz o parsing do valor bruto de `visitor_categories`.

    Aceita múltiplos formatos salvos no banco:
        - "civil,militar,ex-militar"
        - '["civil", "militar", "ex-militar"]'
        - "[civil, militar, ex-militar]"

    Retorna uma lista de strings limpas, sem duplicatas, preservando a ordem.
    """
    if raw is None:
        return []

    raw = str(raw).strip()

    if not raw:
        return []

    items = []

    # 1) Tenta interpretar como JSON (ex.: ["civil","militar"])
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                items = [str(x) for x in parsed]
        except (ValueError, TypeError):
            # 2) Fallback: remove colchetes e divide por vírgula
            inner = raw[1:-1]
            items = inner.split(",")
    else:
        # 3) Formato padrão separado por vírgula
        items = raw.split(",")

    values = []
    seen = set()

    for item in items:
        value = str(item).strip().strip('"').strip("'")

        if not value:
            continue
        if value in seen:
            continue

        seen.add(value)
        values.append(value)

    return values


def get_visitor_categories(include_inactive: bool = False) -> list[dict]:
    """
    Retorna as categorias de visitante.

    Agora lê da tabela `visitor_categories`. Mantém o MESMO formato de dict
    (value/label/icon/btn_class/badge_class) para não quebrar o wizard.
    """
    # Import local evita import circular
    from app.models.visitor_category import VisitorCategory

    query = VisitorCategory.query
    if not include_inactive:
        query = query.filter_by(is_active=True)

    rows = query.order_by(
        VisitorCategory.sort_order.asc(),
        VisitorCategory.label.asc(),
    ).all()

    categories = [
        {
            "value": row.value,
            "label": row.label,
            "icon": row.icon or "bi-tag",
            "btn_class": row.btn_class or "btn-outline-secondary",
            "badge_class": row.badge_class or "bg-secondary",
        }
        for row in rows
    ]

    # Fallback de segurança (banco vazio)
    if not categories:
        categories.append({
            "value": "civil",
            "label": "Civil",
            "icon": "bi-person",
            "btn_class": "btn-outline-secondary",
            "badge_class": "bg-secondary",
        })

    return categories

