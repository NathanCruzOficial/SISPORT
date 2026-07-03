# app/models/visitor_category.py
"""Modelo e helpers para categorias de visitante."""

import re

from app.extensions import db


class VisitorCategory(db.Model):
    __tablename__ = "visitor_categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Slug estável para import/export e compatibilidade com dados antigos.
    # Ex.: "civil", "militar", "ex-militar"
    value = db.Column(db.String(60), unique=True, nullable=False)

    label = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(60), default="bi-tag")
    btn_class = db.Column(db.String(60), default="btn-outline-secondary")
    badge_class = db.Column(db.String(60), default="bg-secondary")
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self) -> str:
        return f"<VisitorCategory {self.value!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "value": self.value,
            "label": self.label,
            "icon": self.icon,
            "btn_class": self.btn_class,
            "badge_class": self.badge_class,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


# =====================================================================
# Categorias padrão obrigatórias do sistema
# =====================================================================

DEFAULT_VISITOR_CATEGORIES = [
    {
        "value": "civil",
        "label": "Civil",
        "icon": "bi-person",
        "btn_class": "btn-outline-secondary",
        "badge_class": "bg-secondary",
        "sort_order": 10,
        "is_active": True,
    },
    {
        "value": "militar",
        "label": "Militar",
        "icon": "bi-shield-fill",
        "btn_class": "btn-outline-success",
        "badge_class": "text-bg-success",
        "sort_order": 20,
        "is_active": True,
    },
]


def slugify_category(text: str) -> str:
    """Converte 'Ex Militar!' -> 'ex-militar'."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "categoria"


def get_active_visitor_categories():
    """Retorna categorias ativas ordenadas para formulários."""
    return (
        VisitorCategory.query
        .filter_by(is_active=True)
        .order_by(
            VisitorCategory.sort_order.asc(),
            VisitorCategory.label.asc(),
        )
        .all()
    )


def get_all_visitor_categories():
    """Retorna todas as categorias ordenadas para administração e relatórios."""
    return (
        VisitorCategory.query
        .order_by(
            VisitorCategory.sort_order.asc(),
            VisitorCategory.label.asc(),
        )
        .all()
    )


def get_visitor_category_by_id(category_id: int | None, active_only: bool = False):
    """Busca categoria por ID, opcionalmente exigindo que esteja ativa."""
    if not category_id:
        return None

    query = VisitorCategory.query.filter_by(id=category_id)

    if active_only:
        query = query.filter_by(is_active=True)

    return query.first()


def get_visitor_category_by_value(value: str | None, active_only: bool = False):
    """Busca categoria por value/slug, útil para importação e compatibilidade."""
    value = (value or "").strip().lower()

    if not value:
        return None

    query = VisitorCategory.query.filter_by(value=value)

    if active_only:
        query = query.filter_by(is_active=True)

    return query.first()


def get_default_visitor_category():
    """
    Retorna a categoria padrão.

    Prioridade:
    1. Categoria value='civil' ativa
    2. Primeira categoria ativa
    3. None
    """
    civil = get_visitor_category_by_value("civil", active_only=True)

    if civil:
        return civil

    return (
        VisitorCategory.query
        .filter_by(is_active=True)
        .order_by(
            VisitorCategory.sort_order.asc(),
            VisitorCategory.label.asc(),
        )
        .first()
    )


def ensure_default_visitor_categories():
    """
    Garante que as categorias padrão obrigatórias existam no banco:

    - civil
    - militar
    - ex-militar

    A função é idempotente:
    pode ser executada várias vezes sem duplicar registros.

    Ela cria categorias ausentes e atualiza os campos visuais das existentes.
    """
    categories_by_value = {
        c.value: c
        for c in VisitorCategory.query.filter(
            VisitorCategory.value.in_(
                [item["value"] for item in DEFAULT_VISITOR_CATEGORIES]
            )
        ).all()
    }

    created_or_updated = []

    for item in DEFAULT_VISITOR_CATEGORIES:
        category = categories_by_value.get(item["value"])

        if category:
            category.label = item["label"]
            category.icon = item["icon"]
            category.btn_class = item["btn_class"]
            category.badge_class = item["badge_class"]
            category.sort_order = item["sort_order"]
            category.is_active = True
        else:
            category = VisitorCategory(**item)
            db.session.add(category)

        created_or_updated.append(category)

    db.session.commit()

    return created_or_updated


def ensure_default_visitor_category():
    """
    Compatibilidade com chamadas antigas.

    Antes garantia apenas Civil.
    Agora garante todas as categorias padrão e retorna a categoria Civil.
    """
    ensure_default_visitor_categories()
    return get_default_visitor_category()
