# =====================================================================
# visitor_controller.py
# Controller de Visitantes — SISPORT V2
# Gerencia wizard (3 etapas), busca por CPF, foto (BLOB no banco),
# check-in/check-out.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import uuid
from datetime import datetime

from flask import session
from sqlalchemy import or_

from ..extensions import db
from ..models.visitor import Visitor, Visit, TempPhoto
from ..models.visitor_category import (
    VisitorCategory,
    get_active_visitor_categories,
    get_visitor_category_by_id,
    get_visitor_category_by_value,
    get_default_visitor_category,
)

from ..utils.photo import parse_photo_data_url
from ..utils.validators import normalize_cpf, is_valid_cpf, validate_required_email


# =====================================================================
# Helpers — Categorias (dinâmicas via banco)
# =====================================================================

def _active_categories():
    """
    Retorna lista de categorias ativas, ordenadas.
    Mantido como wrapper para compatibilidade interna.
    """
    return get_active_visitor_categories()


def _resolve_active_category_by_id(category_id) -> VisitorCategory:
    """
    Valida e retorna uma categoria ativa pelo ID.

    Usado no wizard e edição de visitante.
    """
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        raise ValueError("Categoria inválida.")

    category = get_visitor_category_by_id(
        category_id,
        active_only=True,
    )

    if not category:
        raise ValueError("Categoria inválida ou inativa.")

    return category


def _resolve_category_from_wizard_data(w: dict) -> VisitorCategory:
    """
    Resolve a categoria salva no wizard.

    Novo padrão:
        w["category_id"]

    Compatibilidade temporária:
        w["category"] = "civil"
    """
    category_id = w.get("category_id")

    if category_id:
        try:
            category = get_visitor_category_by_id(
                int(category_id),
                active_only=False,
            )
            if category:
                return category
        except (TypeError, ValueError):
            pass

    # Compatibilidade com sessão antiga usando string
    old_category_value = (w.get("category") or "").strip().lower()

    if old_category_value:
        category = get_visitor_category_by_value(
            old_category_value,
            active_only=False,
        )

        if category:
            return category

    category = get_default_visitor_category()

    if not category:
        raise ValueError(
            "Nenhuma categoria de visitante disponível. "
            "Cadastre pelo menos uma categoria ativa."
        )

    return category


def _default_category_id() -> int | None:
    """
    Retorna o ID da categoria padrão, se existir.
    """
    category = get_default_visitor_category()
    return category.id if category else None



# =====================================================================
# Funções — Busca de Visitante
# =====================================================================

def find_visitor_by_cpf(cpf: str):
    """
    Busca visitante cadastrado pelo CPF.

    :param cpf: (str) CPF do visitante (com ou sem formatação).
    :return: Instância de Visitor se encontrado, ou None.
    """
    cpf = (cpf or "").strip()
    return db.session.query(Visitor).filter(Visitor.cpf == cpf).one_or_none()


# =====================================================================
# Funções — Wizard de Cadastro (Etapas 1, 2 e finalização)
# =====================================================================

def wizard_start_for_new_visitor(cpf: str = ""):
    """
    Inicializa a sessão do wizard para um novo cadastro de visitante.

    :param cpf: (str) CPF pré-preenchido (opcional).
    :return: None — os dados são gravados em session["wizard"].
    """
    session["wizard"] = {
        "mode": "new",
        "step": 1,
        "name": "",
        "cpf": (cpf or "").strip(),
        "phone": "",
        "email": None,
        "empresa": "",
        "father_name": "",
        "mom_name": "",
        "category_id": _default_category_id(),
        "temp_photo_id": None,      # ← ID da foto na tabela temp_photos
        "photo_captured": False,     # ← indica se capturou foto
    }


def _check_duplicate_fields(name: str, father_name: str, mom_name: str,
                            cpf: str, phone: str, email: str | None,
                            exclude_id: int | None = None):
    """
    Verifica se algum dos campos informados já pertence a um visitante
    cadastrado no banco de dados. Se encontrar duplicidade, levanta
    ValueError com a lista detalhada de conflitos.
    """
    filters = [
        Visitor.cpf == cpf,
        Visitor.name == name,
        Visitor.mom_name == mom_name,
        Visitor.phone == phone,
    ]

    if father_name:
        filters.append(Visitor.father_name == father_name)

    if email:
        filters.append(Visitor.email == email)

    query = db.session.query(Visitor).filter(or_(*filters))

    if exclude_id is not None:
        query = query.filter(Visitor.id != exclude_id)

    matches = query.all()

    if not matches:
        return

    conflicts = []
    for visitor in matches:
        visitor_label = f"{visitor.name} (CPF: {visitor.cpf})"
        if visitor.cpf == cpf:
            conflicts.append(f"• CPF já cadastrado por: {visitor_label}")
        if visitor.name == name:
            conflicts.append(f"• Nome completo já cadastrado por: {visitor_label}")
        if visitor.mom_name == mom_name:
            conflicts.append(f"• Nome da mãe já cadastrado por: {visitor_label}")
        if visitor.phone == phone:
            conflicts.append(f"• Telefone já cadastrado por: {visitor_label}")
        if father_name and visitor.father_name == father_name:
            conflicts.append(f"• Nome do pai já cadastrado por: {visitor_label}")
        if email and visitor.email == email:
            conflicts.append(f"• E-mail já cadastrado por: {visitor_label}")

    detail = "\n".join(conflicts)
    raise ValueError(
        f"Dados já em uso por visitante(s) cadastrado(s):\n{detail}\n"
        f"Utilize a busca por CPF para localizar o registro existente."
    )

def wizard_create_visitor_and_finish() -> Visitor:
    """
    Cria o visitante definitivo a partir dos dados do wizard,
    limpa a foto temporária e encerra a sessão do wizard.
    """
    visitor = create_visitor_if_not_exists_from_wizard()
    session.pop("wizard", None)
    return visitor



def wizard_step1_submit(name: str, father_name: str, mom_name: str,
                        cpf: str, phone: str, email: str, empresa: str,
                        category_id=None):
    """
    Processa e valida os dados da Etapa 1 do wizard.

    Agora a categoria é recebida como category_id, Foreign Key
    para VisitorCategory.
    """
    w = session.get("wizard") or {}

    name = (name or "").strip().upper()
    father_name = (father_name or "").strip().upper()
    mom_name = (mom_name or "").strip().upper()
    empresa = (empresa or "").strip().upper()

    category = _resolve_active_category_by_id(category_id)

    cpf = normalize_cpf(cpf or "")

    if not is_valid_cpf(cpf):
        raise ValueError("CPF inválido. Verifique e tente novamente.")

    phone = (phone or "").strip()

    if not phone:
        raise ValueError("Telefone/Celular é obrigatório.")

    email = (email or "").strip()

    if email:
        email = validate_required_email(email).lower()
    else:
        email = None

    if not name:
        raise ValueError("Nome completo é obrigatório.")

    if not mom_name:
        raise ValueError("Nome da mãe é obrigatório.")

    _check_duplicate_fields(
        name=name,
        father_name=father_name,
        mom_name=mom_name,
        cpf=cpf,
        phone=phone,
        email=email,
    )

    w.update({
        "name": name,
        "father_name": father_name,
        "mom_name": mom_name,
        "cpf": cpf,
        "phone": phone,
        "email": email,
        "empresa": empresa,
        "category_id": category.id,
        "step": 2,
    })

    # Remove chave antiga, caso exista de sessões anteriores
    w.pop("category", None)

    session["wizard"] = w



def wizard_step2_submit(photo_data_url: str | None):
    """
    Processa a Etapa 2 do wizard: recebe a foto (data URL), decodifica
    e salva na tabela temporária.
    """
    w = session.get("wizard") or {}
    cpf = (w.get("cpf") or "").strip()
    if not cpf:
        raise ValueError("CPF não informado. Volte à etapa 1.")

    photo_data_url = (photo_data_url or "").strip()

    if photo_data_url:
        # ── Decodifica a foto e salva no banco temporário ─────────
        photo_bytes, photo_mime = parse_photo_data_url(photo_data_url)

        temp_id = w.get("temp_photo_id") or str(uuid.uuid4())

        existing_temp = db.session.get(TempPhoto, temp_id)
        if existing_temp:
            existing_temp.photo_data     = photo_bytes
            existing_temp.photo_mimetype = photo_mime
        else:
            db.session.add(TempPhoto(
                id=temp_id,
                photo_data=photo_bytes,
                photo_mimetype=photo_mime,
            ))
        db.session.commit()

        w["temp_photo_id"]  = temp_id
        w["photo_captured"] = True
    else:
        # ── Foto pulada — limpa referência anterior se existir ────
        old_id = w.get("temp_photo_id")
        if old_id:
            old_temp = db.session.get(TempPhoto, old_id)
            if old_temp:
                db.session.delete(old_temp)
                db.session.commit()

        w["temp_photo_id"]  = None
        w["photo_captured"] = False

    # ── O wizard agora tem apenas 2 etapas ─────────────────────
    w["step"] = 2
    session["wizard"] = w




def create_visitor_if_not_exists_from_wizard() -> Visitor:
    """
    Finaliza o wizard: cria o visitante no banco de dados a partir dos
    dados da sessão.

    A foto é recuperada da tabela temp_photos e salva como BLOB no
    registro definitivo do visitante.
    """
    w = session.get("wizard") or {}

    name = (w.get("name") or "").strip()
    father_name = (w.get("father_name") or "").strip()
    mom_name = (w.get("mom_name") or "").strip()
    cpf = (w.get("cpf") or "").strip()
    phone = (w.get("phone") or "").strip()
    email = w.get("email") or None
    empresa = (w.get("empresa") or "").strip()

    category = _resolve_category_from_wizard_data(w)

    if not name or not cpf or not phone or not mom_name:
        raise ValueError("Cadastro incompleto: nome, CPF, telefone e nome da mãe são obrigatórios.")

    existing = find_visitor_by_cpf(cpf)

    if existing:
        _cleanup_temp_photo(w.get("temp_photo_id"))
        return existing

    photo_bytes = None
    photo_mime = None

    temp_id = w.get("temp_photo_id")

    if temp_id:
        temp = db.session.get(TempPhoto, temp_id)

        if temp:
            photo_bytes = temp.photo_data
            photo_mime = temp.photo_mimetype
            db.session.delete(temp)

    visitor = Visitor(
        name=name,
        cpf=cpf,
        phone=phone,
        email=email,
        empresa=empresa,
        father_name=father_name or None,
        mom_name=mom_name,
        category_id=category.id,
        photo_data=photo_bytes,
        photo_mimetype=photo_mime,
    )

    db.session.add(visitor)
    db.session.commit()

    return visitor



def _cleanup_temp_photo(temp_id: str | None):
    """Remove foto temporária do banco, se existir."""
    if not temp_id:
        return
    temp = db.session.get(TempPhoto, temp_id)
    if temp:
        db.session.delete(temp)
        db.session.commit()


# =====================================================================
# Funções — Foto de Visitante
# =====================================================================

def visitor_photo_update(visitor, photo_data_url):
    """
    Atualiza a foto de perfil de um visitante já cadastrado.
    """
    photo_bytes, photo_mime = parse_photo_data_url(photo_data_url)
    visitor.photo_data     = photo_bytes
    visitor.photo_mimetype = photo_mime
    db.session.commit()  # ← direto no banco, zero sessão



# =====================================================================
# Funções — Check-in / Check-out de Visitas
# =====================================================================

def register_checkin(visitor: Visitor, destination: str, reason: str = "") -> int:
    """
    Registra uma nova entrada/check-in para um visitante.

    destination:
        Local selecionado na árvore de destinos.

    reason:
        Motivo da visita. Pode ser obrigatório ou opcional conforme configuração.
    """
    destination = (destination or "").strip()
    reason = (reason or "").strip()

    if not destination:
        raise ValueError("Selecione o local/destino da visita.")

    visit = Visit(
        visitor_id=visitor.id,
        destination=destination,
        reason=reason,
        check_in=datetime.now(),
    )

    db.session.add(visit)
    db.session.commit()

    return visit.id



def checkout_visit(visit_id: int, checkout_time: datetime = None):
    """
    Registra a saída (check-out) de uma visita em aberto.
    Se checkout_time for fornecido, usa-o; senão, usa datetime.now().
    """
    visit = db.session.get(Visit, visit_id)
    if not visit:
        raise ValueError("Visita não encontrada.")
    if visit.check_out is None:
        visit.check_out = checkout_time if checkout_time else datetime.now()
        visit.visitor.last_checkout_at = visit.check_out
        db.session.commit()
    return visit

