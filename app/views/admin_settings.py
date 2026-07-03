# =====================================================================
# views/admin_settings.py
# Blueprint de Configurações Administrativas do SISPORT
# =====================================================================

from __future__ import annotations

import json
import os
import shutil
import re
import unicodedata
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func

from app.extensions import db
from app.models.settings import get_setting, set_setting
from app.models.visitor import Visitor, Visit
from app.models.visitor_destination import (
    VisitorDestinationGroup,
    VisitorDestinationPlace,
)
from app.models.visitor_category import (
    VisitorCategory,
    get_active_visitor_categories,
    get_all_visitor_categories,
    get_visitor_category_by_id,
    get_visitor_category_by_value,
    get_default_visitor_category,
)

from app.defaults import build_snapshot
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
]



# =====================================================================
# Helpers — Snapshot
# =====================================================================

def _settings_snapshot() -> dict:
    """Retorna TODAS as configurações — gerado automaticamente do DEFAULTS."""
    return build_snapshot(get_setting)


# =====================================================================
# Helpers — Grupos e Locais de Visitação
# =====================================================================

DEFAULT_ROOT_NAME = "Raiz"
DEFAULT_ROOT_COLOR = "#ffc107"


def ensure_root_group():
    """Garante que exista pelo menos um grupo raiz."""
    root = VisitorDestinationGroup.query.filter_by(is_root=True).first()

    if root:
        return root

    root = VisitorDestinationGroup(
        name=DEFAULT_ROOT_NAME,
        color=DEFAULT_ROOT_COLOR,
        parent_id=None,
        is_root=True,
        sort_order=0,
    )

    db.session.add(root)
    db.session.commit()

    return root


def flatten_groups(parent_group, depth=0, include_self=True):
    """
    Retorna os grupos em estrutura plana, com propriedade temporária depth.

    Exemplo:
    Raiz depth 0
    Pátio 1 depth 1
    Estado Maior depth 2
    """
    items = []

    if include_self:
        parent_group.depth = depth
        items.append(parent_group)

    children = (
        VisitorDestinationGroup.query
        .filter_by(parent_id=parent_group.id)
        .order_by(
            VisitorDestinationGroup.sort_order.asc(),
            VisitorDestinationGroup.name.asc(),
        )
        .all()
    )

    for child in children:
        child.depth = depth + 1
        items.extend(flatten_groups(child, depth + 1, include_self=True))

    return items


def destination_group_is_ancestor_of(group, possible_child):
    """
    Verifica se 'group' é ancestral de 'possible_child'.

    Usado para impedir que um grupo seja movido para dentro
    de um dos próprios subgrupos.
    """
    current = possible_child.parent

    while current:
        if current.id == group.id:
            return True

        current = current.parent

    return False


def next_destination_sort_order(group_id):
    """Calcula a próxima ordem dentro de um grupo."""
    max_group_order = (
        db.session.query(db.func.max(VisitorDestinationGroup.sort_order))
        .filter_by(parent_id=group_id)
        .scalar()
    )

    max_place_order = (
        db.session.query(db.func.max(VisitorDestinationPlace.sort_order))
        .filter_by(group_id=group_id)
        .scalar()
    )

    values = [
        value
        for value in (max_group_order, max_place_order)
        if value is not None
    ]

    if not values:
        return 1

    return max(values) + 1


def get_destination_group_items(group):
    """Retorna grupos e locais diretamente dentro de um grupo."""
    groups = (
        VisitorDestinationGroup.query
        .filter_by(parent_id=group.id)
        .order_by(
            VisitorDestinationGroup.sort_order.asc(),
            VisitorDestinationGroup.name.asc(),
        )
        .all()
    )

    places = (
        VisitorDestinationPlace.query
        .filter_by(group_id=group.id)
        .order_by(
            VisitorDestinationPlace.sort_order.asc(),
            VisitorDestinationPlace.name.asc(),
        )
        .all()
    )

    items = []

    for group_item in groups:
        items.append({
            "kind": "group",
            "id": group_item.id,
            "name": group_item.name,
            "color": group_item.color,
            "sort_order": group_item.sort_order,
            "object": group_item,
        })

    for place in places:
        items.append({
            "kind": "place",
            "id": place.id,
            "name": place.name,
            "color": place.color,
            "sort_order": place.sort_order,
            "object": place,
        })

    return sorted(
        items,
        key=lambda item: (
            item["sort_order"],
            item["name"].lower(),
        ),
    )


# =====================================================================
# Helpers — Categorias de Visitante
# =====================================================================

def _classes_from_color(color: str) -> tuple[str, str]:
    """
    Converte um nome de cor Bootstrap em (btn_class, badge_class).
    Ex.: "success" -> ("btn-success", "bg-success")
    """
    color = (color or "").strip().lower()
    if color in {"primary", "secondary", "success", "danger", "warning", "info", "dark", "light"}:
        return f"btn-{color}", f"bg-{color}"
    return "btn-outline-secondary", "bg-secondary"


def _next_category_order() -> int:
    max_order = db.session.query(
        db.func.coalesce(db.func.max(VisitorCategory.sort_order), -1)
    ).scalar()
    return max_order + 1


# =====================================================================
# Rotas — Resetar configurações
# =====================================================================

@admin_bp.post("/settings/reset-defaults")
def reset_defaults():
    """Restaura TODAS as configurações para os valores padrão."""
    from app.defaults import DEFAULTS

    # Senha administrativa NUNCA é resetada por segurança
    protected_keys = {"admin_password_hash"}

    restored = 0

    for key, (default_value, _type) in DEFAULTS.items():
        if key not in protected_keys:
            set_setting(key, default_value)
            restored += 1

    db.session.commit()

    flash(f"Configurações restauradas ao padrão ({restored} parâmetros).", "success")

    return redirect(url_for("admin.settings_page", tab_key="general"))


@admin_bp.post("/settings/reset-defaults/<tab_key>")
def reset_tab_defaults(tab_key: str):
    """Restaura apenas as configs de uma aba específica."""
    from app.defaults import DEFAULTS

    tab_prefixes = {
        "general": ("inst_", "header_"),
        "visitors": ("visitor_",),
        "database": ("retention_",),
    }

    prefixes = tab_prefixes.get(tab_key)

    if not prefixes:
        flash("Aba não reconhecida.", "warning")
        return redirect(url_for("admin.settings_page", tab_key=tab_key))

    restored = 0

    for key, (default_value, _type) in DEFAULTS.items():
        if any(key.startswith(prefix) for prefix in prefixes):
            set_setting(key, default_value)
            restored += 1

    db.session.commit()

    flash(f"{restored} configurações desta aba restauradas ao padrão.", "success")

    return redirect(url_for("admin.settings_page", tab_key=tab_key))


# =====================================================================
# Rota — Página de Configurações
# =====================================================================

@admin_bp.get("/settings")
@admin_bp.get("/settings/<tab_key>")
def settings_page(tab_key: str = "general"):
    """Renderiza a página de configurações com a aba selecionada."""
    from app.controllers.config_registry import SETTINGS_TABS

    settings = _settings_snapshot()

    root = ensure_root_group()
    visitor_groups_flat = flatten_groups(root, depth=0, include_self=True)

    current_tab = None

    for tab in SETTINGS_TABS:
        if tab["key"] == tab_key:
            current_tab = tab
            break

    if current_tab is None:
        current_tab = SETTINGS_TABS[0]
        tab_key = current_tab["key"]

    visitor_categories_full = get_all_visitor_categories()

    # ─────────────────────────────────────────────────────────
    # Contagem de visitantes por categoria para o painel
    # ─────────────────────────────────────────────────────────
    count_rows = (
        db.session.query(
            Visitor.category_id,
            func.count(Visitor.id),
        )
        .filter(Visitor.category_id.isnot(None))
        .group_by(Visitor.category_id)
        .all()
    )

    visitor_counts = {cat_id: total for cat_id, total in count_rows}

    return render_template(
        "admin/settings_page.html",
        tabs=SETTINGS_TABS,
        active_tab=tab_key,
        current_tab=current_tab,
        settings=settings,
        visitor_groups_flat=visitor_groups_flat,
        visitor_categories_full=visitor_categories_full,
        visitor_categories=visitor_categories_full,  # garante o nome esperado no template
        visitor_counts=visitor_counts,
    )


# =====================================================================
# Rotas — CRUD de Categorias de Visitante
# =====================================================================

def slugify_category(text):
    text = (text or "").strip().lower()

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    return text or "categoria"

@admin_bp.post("/settings/visitor-categories/create")
def create_visitor_category():
    """Cria uma nova categoria de visitante."""
    label = request.form.get("label", "").strip()
    icon = request.form.get("icon", "").strip() or "bi-tag"

    if not label:
        flash("Informe o nome da categoria.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="visitors"))

    # Preferir 'color' do form; se não vier, aceitar classes diretas
    color = (request.form.get("color") or "").strip().lower()
    default_btn, default_badge = _classes_from_color(color)

    btn_class = (request.form.get("btn_class") or default_btn).strip()
    badge_class = (request.form.get("badge_class") or default_badge).strip()

    value = slugify_category(label)

    if VisitorCategory.query.filter_by(value=value).first():
        flash(f"Já existe uma categoria com o identificador '{value}'.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="visitors"))

    cat = VisitorCategory(
        value=value,
        label=label,
        icon=icon,
        btn_class=btn_class or "btn-outline-secondary",
        badge_class=badge_class or "bg-secondary",
        sort_order=_next_category_order(),
        is_active=True,
    )
    db.session.add(cat)
    db.session.commit()

    flash("Categoria criada com sucesso.", "success")
    return redirect(url_for("admin.settings_page", tab_key="visitors"))


@admin_bp.post("/settings/visitor-categories/<int:cat_id>/edit")
def edit_visitor_category(cat_id: int):
    """Edita uma categoria existente."""
    cat = VisitorCategory.query.get_or_404(cat_id)

    label = request.form.get("label", "").strip()
    if not label:
        flash("Informe o nome da categoria.", "warning")
        return redirect(url_for("admin.settings_page", tab_key="visitors"))

    cat.label = label
    cat.icon = request.form.get("icon", "").strip() or "bi-tag"

    color = (request.form.get("color") or "").strip().lower()
    default_btn, default_badge = _classes_from_color(color)

    cat.btn_class = (request.form.get("btn_class") or default_btn).strip() or "btn-outline-secondary"
    cat.badge_class = (request.form.get("badge_class") or default_badge).strip() or "bg-secondary"
    cat.is_active = bool(request.form.get("is_active"))

    db.session.commit()
    flash("Categoria atualizada.", "success")
    return redirect(url_for("admin.settings_page", tab_key="visitors"))


@admin_bp.route("/settings/visitor-categories/<int:cat_id>/toggle", methods=["POST"])
def toggle_visitor_category(cat_id):
    category = VisitorCategory.query.get_or_404(cat_id)

    category.is_active = not category.is_active

    db.session.commit()

    if category.is_active:
        flash("Categoria ativada com sucesso.", "success")
    else:
        flash("Categoria desativada com sucesso.", "success")

    return redirect(url_for("admin.settings_page"))


@admin_bp.post("/settings/visitor-categories/<int:cat_id>/delete")
def delete_visitor_category(cat_id: int):
    """
    Deleta uma categoria.

    Se houver visitantes vinculados:
    - Com outras categorias disponíveis: exige target_category_id
    - Sem outras categorias: bloqueia (ao menos a Civil deve existir)
    """
    cat = VisitorCategory.query.get_or_404(cat_id)

    visitors_count = Visitor.query.filter_by(category_id=cat.id).count()

    # ── Lista as outras categorias disponíveis ──
    other_categories = (
        VisitorCategory.query
        .filter(VisitorCategory.id != cat.id)
        .order_by(
            VisitorCategory.sort_order.asc(),
            VisitorCategory.label.asc(),
        )
        .all()
    )

    default_cat = get_default_visitor_category()

    if visitors_count > 0:
        if not other_categories:
            flash(
                f"Não é possível deletar a categoria '{cat.label}'. "
                f"Ela possui {visitors_count} visitante(s) vinculado(s) "
                f"e não há outra categoria para migrá-los. "
                f"Cadastre uma nova categoria antes de excluir esta.",
                "danger",
            )
            return redirect(url_for("admin.settings_page", tab_key="visitors"))

        # ── Se só existe a categoria padrão como alternativa,
        #     migra automaticamente ──
        if len(other_categories) == 1:
            target = other_categories[0]
        else:
            target_id = request.form.get("target_category_id", type=int)

            if not target_id:
                flash(
                    "É necessário selecionar uma categoria de destino "
                    "para migrar os visitantes vinculados.",
                    "warning",
                )
                return redirect(url_for("admin.settings_page", tab_key="visitors"))

            if target_id == cat.id:
                flash(
                    "A categoria de destino não pode ser a mesma "
                    "que está sendo excluída.",
                    "warning",
                )
                return redirect(url_for("admin.settings_page", tab_key="visitors"))

            target = VisitorCategory.query.get(target_id)

            if not target:
                flash("Categoria de destino inválida.", "danger")
                return redirect(url_for("admin.settings_page", tab_key="visitors"))

        # ── Migra os visitantes ──
        Visitor.query.filter_by(category_id=cat.id).update(
            {"category_id": target.id}
        )
        db.session.flush()

        db.session.delete(cat)
        db.session.commit()

        flash(
            f"Categoria '{cat.label}' deletada. "
            f"{visitors_count} visitante(s) migrado(s) "
            f"para '{target.label}'.",
            "success",
        )
        return redirect(url_for("admin.settings_page", tab_key="visitors"))

    # ── Sem visitantes vinculados: exclusão direta ──
    db.session.delete(cat)
    db.session.commit()

    flash(f"Categoria '{cat.label}' deletada.", "success")
    return redirect(url_for("admin.settings_page", tab_key="visitors"))


@admin_bp.post("/settings/visitor-categories/reorder")
def reorder_visitor_categories():
    """Reordena categorias (drag & drop via JSON)."""
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("ids", [])

    for index, cat_id in enumerate(ordered_ids):
        cat = VisitorCategory.query.get(cat_id)
        if cat:
            cat.sort_order = index

    db.session.commit()
    return jsonify({"success": True})


# =====================================================================
# Rotas — Grupos e Locais de Visitação
# =====================================================================

@admin_bp.get("/visitor-destinations")
def visitor_destinations_root():
    """Redireciona para o grupo raiz."""
    root = ensure_root_group()

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=root.id)
    )


@admin_bp.get("/visitor-destinations/groups/<int:group_id>")
def visitor_destinations_group(group_id: int):
    """Página de gerenciamento de uma categoria/grupo."""
    root = ensure_root_group()

    current_group = VisitorDestinationGroup.query.get_or_404(group_id)
    groups_flat = flatten_groups(root, depth=0, include_self=True)
    children_items = get_destination_group_items(current_group)

    return render_template(
        "admin/visitor_destinations_group.html",
        root=root,
        current_group=current_group,
        groups_flat=groups_flat,
        children_items=children_items,
    )


@admin_bp.post("/visitor-destinations/groups/create")
def create_visitor_destination_group():
    """Cria um novo grupo/categoria."""
    root = ensure_root_group()

    name = request.form.get("name", "").strip()
    color = request.form.get("color", DEFAULT_ROOT_COLOR).strip()
    parent_id = request.form.get("parent_id", type=int)

    if not parent_id:
        parent_id = root.id

    parent_group = VisitorDestinationGroup.query.get(parent_id)

    if not parent_group:
        flash("Grupo pai inválido.", "danger")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=root.id)
        )

    if not name:
        flash("Informe o nome do grupo.", "warning")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=parent_group.id)
        )

    group = VisitorDestinationGroup(
        name=name,
        color=color or DEFAULT_ROOT_COLOR,
        parent_id=parent_group.id,
        is_root=False,
        sort_order=next_destination_sort_order(parent_group.id),
    )

    db.session.add(group)
    db.session.commit()

    flash("Grupo criado com sucesso.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=parent_group.id)
    )


@admin_bp.post("/visitor-destinations/groups/<int:group_id>/edit")
def edit_visitor_destination_group(group_id: int):
    """Edita um grupo/categoria."""
    root = ensure_root_group()

    group = VisitorDestinationGroup.query.get_or_404(group_id)

    name = request.form.get("name", "").strip()
    color = request.form.get("color", DEFAULT_ROOT_COLOR).strip()
    parent_id = request.form.get("parent_id", type=int)

    if not name:
        flash("Informe o nome do grupo.", "warning")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=group.id)
        )

    group.name = name
    group.color = color or DEFAULT_ROOT_COLOR

    if not group.is_root:
        if not parent_id:
            parent_id = root.id

        new_parent = VisitorDestinationGroup.query.get(parent_id)

        if not new_parent:
            flash("Grupo pai inválido.", "danger")
            return redirect(
                url_for("admin.visitor_destinations_group", group_id=group.id)
            )

        if new_parent.id == group.id:
            flash("Um grupo não pode ser pai dele mesmo.", "danger")
            return redirect(
                url_for("admin.visitor_destinations_group", group_id=group.id)
            )

        if destination_group_is_ancestor_of(group, new_parent):
            flash(
                "Você não pode mover um grupo para dentro de um dos seus próprios subgrupos.",
                "danger",
            )
            return redirect(
                url_for("admin.visitor_destinations_group", group_id=group.id)
            )

        old_parent_id = group.parent_id
        group.parent_id = new_parent.id

        if old_parent_id != new_parent.id:
            group.sort_order = next_destination_sort_order(new_parent.id)

    db.session.commit()

    flash("Grupo atualizado com sucesso.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=group.id)
    )


@admin_bp.post("/visitor-destinations/groups/<int:group_id>/delete")
def delete_visitor_destination_group(group_id: int):
    """Deleta um grupo e tudo que existe dentro dele."""
    root = ensure_root_group()

    group = VisitorDestinationGroup.query.get_or_404(group_id)

    if group.is_root:
        flash("O grupo raiz não pode ser deletado.", "danger")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=root.id)
        )

    parent_id = group.parent_id or root.id

    db.session.delete(group)
    db.session.commit()

    flash("Grupo e todos os seus itens internos foram deletados.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=parent_id)
    )


@admin_bp.post("/visitor-destinations/places/create")
def create_visitor_destination_place():
    """Cria um local dentro de um grupo."""
    root = ensure_root_group()

    name = request.form.get("name", "").strip()
    group_id = request.form.get("group_id", type=int)
    is_active = bool(request.form.get("is_active"))

    if not group_id:
        group_id = root.id

    group = VisitorDestinationGroup.query.get(group_id)

    if not group:
        flash("Grupo inválido.", "danger")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=root.id)
        )

    if not name:
        flash("Informe o nome do local.", "warning")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=group.id)
        )

    place = VisitorDestinationPlace(
        name=name,
        group_id=group.id,
        is_active=is_active,
        sort_order=next_destination_sort_order(group.id),
    )

    db.session.add(place)
    db.session.commit()

    flash("Local criado com sucesso.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=group.id)
    )


@admin_bp.post("/visitor-destinations/places/<int:place_id>/edit")
def edit_visitor_destination_place(place_id: int):
    """Edita um local."""
    root = ensure_root_group()

    place = VisitorDestinationPlace.query.get_or_404(place_id)

    name = request.form.get("name", "").strip()
    group_id = request.form.get("group_id", type=int)
    is_active = bool(request.form.get("is_active"))

    if not group_id:
        group_id = root.id

    group = VisitorDestinationGroup.query.get(group_id)

    if not group:
        flash("Grupo inválido.", "danger")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=place.group_id)
        )

    if not name:
        flash("Informe o nome do local.", "warning")
        return redirect(
            url_for("admin.visitor_destinations_group", group_id=place.group_id)
        )

    old_group_id = place.group_id

    place.name = name
    place.group_id = group.id
    place.is_active = is_active

    if old_group_id != group.id:
        place.sort_order = next_destination_sort_order(group.id)

    db.session.commit()

    flash("Local atualizado com sucesso.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=group.id)
    )


@admin_bp.post("/visitor-destinations/places/<int:place_id>/toggle")
def toggle_visitor_destination_place(place_id: int):
    """Ativa ou desativa um local."""
    place = VisitorDestinationPlace.query.get_or_404(place_id)

    place.is_active = not place.is_active

    db.session.commit()

    flash("Status do local atualizado.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=place.group_id)
    )


@admin_bp.post("/visitor-destinations/places/<int:place_id>/delete")
def delete_visitor_destination_place(place_id: int):
    """Deleta um local."""
    root = ensure_root_group()

    place = VisitorDestinationPlace.query.get_or_404(place_id)
    group_id = place.group_id or root.id

    db.session.delete(place)
    db.session.commit()

    flash("Local deletado com sucesso.", "success")

    return redirect(
        url_for("admin.visitor_destinations_group", group_id=group_id)
    )


@admin_bp.post("/visitor-destinations/reorder")
def reorder_visitor_destinations():
    """Reordena grupos e locais dentro de um grupo."""
    data = request.get_json(silent=True) or {}

    group_id = data.get("group_id")
    ordered_items = data.get("items", [])

    group = VisitorDestinationGroup.query.get(group_id)

    if not group:
        return jsonify({
            "success": False,
            "message": "Grupo inválido.",
        }), 400

    for index, item in enumerate(ordered_items, start=1):
        item_type = item.get("type")
        item_id = item.get("id")

        if item_type == "group":
            group_item = VisitorDestinationGroup.query.get(item_id)

            if group_item and group_item.parent_id == group.id:
                group_item.sort_order = index

        elif item_type == "place":
            place = VisitorDestinationPlace.query.get(item_id)

            if place and place.group_id == group.id:
                place.sort_order = index

    db.session.commit()

    return jsonify({
        "success": True,
    })


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
    """Salva campos obrigatórios e regras de visita."""
    set_setting(
        "visitor_father_name_required",
        "1" if request.form.get("father_name_required") else "0",
    )
    set_setting(
        "visitor_email_required",
        "1" if request.form.get("email_required") else "0",
    )
    set_setting(
        "visitor_empresa_required",
        "1" if request.form.get("empresa_required") else "0",
    )
    set_setting(
        "visitor_visit_reason_required",
        "1" if (
            request.form.get("visit_reason_required")
            or request.form.get("visitor_visit_reason_required")
        ) else "0",
    )

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
    set_setting(
        "retention_action",
        action if action in ("delete", "anonymize") else "delete",
    )
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
    data = request.get_json(silent=True) or {}
    days = int(data.get("retention_days", 0))

    if days <= 0:
        return jsonify({"count": 0})

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

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

    for visitor in visitors:
        if action == "delete":
            if visitor.photo_rel_path:
                photo_full = UPLOADS_DIR / visitor.photo_rel_path

                if photo_full.is_file():
                    photo_full.unlink(missing_ok=True)

            Visit.query.filter_by(visitor_id=visitor.id).delete()

            db.session.delete(visitor)

        else:
            visitor.name = "ANONIMIZADO"
            visitor.doc_number = f"ANON-{visitor.id}"
            visitor.mom_name = ""
            visitor.phone = ""
            visitor.email = ""

            if del_photo and visitor.photo_rel_path:
                photo_full = UPLOADS_DIR / visitor.photo_rel_path

                if photo_full.is_file():
                    photo_full.unlink(missing_ok=True)

                visitor.photo_rel_path = ""

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
    """Exporta configurações, exceto senha, como arquivo JSON."""
    data = {}

    for key in _EXPORTABLE_KEYS:
        data[key] = get_setting(key, "")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
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

    except Exception as error:
        db.session.rollback()
        flash(f"Erro ao importar: {error}", "danger")

    return redirect(url_for("admin.settings_page", tab_key="database"))


# =====================================================================
# Rotas — Exportar Visitantes e Visitas (JSON)
# =====================================================================

@admin_bp.get("/settings/export-visitors")
def export_visitors():
    """Exporta todos os visitantes e suas visitas como JSON."""
    visitors = Visitor.query.order_by(Visitor.id.asc()).all()

    records = []

    for visitor in visitors:
        visits_data = []

        visits = (
            Visit.query
            .filter_by(visitor_id=visitor.id)
            .order_by(Visit.id.asc())
            .all()
        )

        for visit in visits:
            visits_data.append({
                "destination": visit.destination,
                "reason": visit.reason,
                "badge_number": visit.badge_number,
                "check_in": visit.check_in.isoformat() if visit.check_in else None,
                "check_out": visit.check_out.isoformat() if visit.check_out else None,
            })

        records.append({
            "name": visitor.name,
            "doc_type": visitor.doc_type,
            "doc_number": visitor.doc_number,
            "mom_name": visitor.mom_name,
            "phone": visitor.phone,
            "email": visitor.email,
            "category_id": visitor.category_id,
            "category_value": visitor.category.value if visitor.category else None,
            "category_label": visitor.category.label if visitor.category else None,
            "photo_rel_path": visitor.photo_rel_path,
            "last_checkout_at": (
                visitor.last_checkout_at.isoformat()
                if visitor.last_checkout_at
                else None
            ),
            "visits": visits_data,
        })

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_visitors": len(records),
        "total_visits": sum(len(record["visits"]) for record in records),
        "visitors": records,
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

    Duplicatas, usando doc_type + doc_number, são ignoradas.
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
            doc_type = record.get("doc_type", "").strip()
            doc_number = record.get("doc_number", "").strip()

            if not doc_number:
                skipped += 1
                continue

            category = None

            category_value = (
                record.get("category_value")
                or record.get("category")
                or "civil"
            )

            category = get_visitor_category_by_value(category_value, active_only=False)

            if not category:
                category = get_default_visitor_category()

            if not category:
                raise ValueError(
                    "Nenhuma categoria de visitante disponível. "
                    "Cadastre pelo menos a categoria Civil."
                )


            existing = Visitor.query.filter_by(
                doc_type=doc_type,
                doc_number=doc_number,
            ).first()

            if existing:
                skipped += 1
                continue

            visitor = Visitor(
                name=record.get("name", ""),
                doc_type=doc_type,
                doc_number=doc_number,
                mom_name=record.get("mom_name", ""),
                phone=record.get("phone", ""),
                email=record.get("email", ""),
                category_id=category.id,
                photo_rel_path=record.get("photo_rel_path", ""),
            )



            last_checkout_at = record.get("last_checkout_at")

            if last_checkout_at:
                try:
                    visitor.last_checkout_at = datetime.fromisoformat(last_checkout_at)
                except (ValueError, TypeError):
                    visitor.last_checkout_at = None

            db.session.add(visitor)
            db.session.flush()

            for visit_data in record.get("visits", []):
                check_in = None
                check_out = None

                try:
                    check_in_raw = visit_data.get("check_in")

                    if check_in_raw:
                        check_in = datetime.fromisoformat(check_in_raw)

                    check_out_raw = visit_data.get("check_out")

                    if check_out_raw:
                        check_out = datetime.fromisoformat(check_out_raw)

                except (ValueError, TypeError):
                    pass

                visit = Visit(
                    visitor_id=visitor.id,
                    destination=visit_data.get("destination", ""),
                    reason=visit_data.get("reason", ""),
                    badge_number=visit_data.get("badge_number", ""),
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
        db.session.rollback()
        flash("Arquivo JSON inválido.", "danger")

    except Exception as error:
        db.session.rollback()
        flash(f"Erro ao importar: {error}", "danger")

    return redirect(url_for("admin.settings_page", tab_key="database"))
