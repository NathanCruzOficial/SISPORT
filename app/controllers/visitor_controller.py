from datetime import datetime
import email
from flask import session
from ..extensions import db
from ..models.visitor import Visitor, Visit
from ..services.photo_service import save_or_replace_profile_photo
from ..utils.validators import normalize_cpf, is_valid_cpf, validate_required_email


def find_visitor_by_cpf(cpf: str):
    """Busca visitante cadastrado pelo CPF."""
    cpf = (cpf or "").strip()
    return db.session.query(Visitor).filter(Visitor.cpf == cpf).one_or_none()

def wizard_start_for_new_visitor(cpf: str = ""):
    """
    Inicializa wizard apenas para novo cadastro.
    Não guarda imagem base64 na sessão.
    """
    session["wizard"] = {
        "mode": "new",
        "step": 1,
        "name": "",
        "cpf": (cpf or "").strip(),
        "phone": "",
        "email": None,  # ← use None, não string vazia
        "empresa": "",
        "father_name": "",
        "mom_name": "",
        "photo_rel_path": "",
    }


def wizard_step1_submit(name: str, father_name: str, mom_name: str,
                       cpf: str, phone: str, email: str, empresa: str):
    w = session.get("wizard") or {}

    # Maiúsculo para nomes e empresa
    name = (name or "").strip().upper()
    father_name = (father_name or "").strip().upper()
    mom_name = (mom_name or "").strip().upper()
    empresa = (empresa or "").strip().upper()

    cpf = normalize_cpf(cpf or "")
    if not is_valid_cpf(cpf):
        raise ValueError("CPF inválido. Verifique e tente novamente.")

    phone = (phone or "").strip()
    if not phone:
        raise ValueError("Telefone/Celular é obrigatório.")
    
    # E-mail opcional, sempre minúsculo quando presente
    email = (email or "").strip()
    if email:
        email = validate_required_email(email).lower()
    else:
        email = None

    if not name:
        raise ValueError("Nome completo é obrigatório.")
    if not mom_name:
        raise ValueError("Nome da mãe é obrigatório.")

    w.update({
        "name": name,
        "father_name": father_name,
        "mom_name": mom_name,
        "cpf": cpf,
        "phone": phone,
        "email": email,   # None ou minúsculo
        "empresa": empresa,
        "step": 2
    })
    session["wizard"] = w




    

def wizard_step2_submit(photo_data_url: str | None):
    """Etapa 2: salva foto (opcional) e vai para etapa 3."""
    w = session.get("wizard") or {}
    cpf = (w.get("cpf") or "").strip()
    if not cpf:
        raise ValueError("CPF não informado. Volte à etapa 1.")

    photo_data_url = (photo_data_url or "").strip()
    photo_rel_path = None
    if photo_data_url:
        photo_rel_path = save_or_replace_profile_photo(photo_data_url, cpf)

    w.update({"photo_rel_path": photo_rel_path, "step": 3})
    session["wizard"] = w


def visitor_photo_update(visitor: Visitor, photo_data_url: str):
    """Atualiza foto de visitante já cadastrado (pode ser feita tanto pelo wizard quanto pela edição de visitante)."""
    if not visitor.cpf:
        raise ValueError("Visitante sem CPF não pode ter foto vinculada.")
    photo_rel_path = save_or_replace_profile_photo(photo_data_url, visitor.cpf)
    visitor.photo_rel_path = photo_rel_path
    db.session.commit()



'''
import base64, os, re
from flask import current_app
from ..extensions import db

def visitor_photo_update(visitor: Visitor, photo_data_url: str) -> None:
    m = re.match(r"^data:image/(png|jpeg|jpg);base64,(.+)$", (photo_data_url or "").strip(), re.I)
    if not m:
        raise ValueError("Foto inválida.")

    ext = m.group(1).lower()
    ext = "jpg" if ext in ("jpeg", "jpg") else "png"
    img_bytes = base64.b64decode(m.group(2), validate=True)

    base = current_app.config["UPLOAD_FOLDER"]          # EX: app/uploads
    folder = os.path.join(base, visitor.cpf)            # EX: app/uploads/<cpf>
    os.makedirs(folder, exist_ok=True)

    filename = f"foto.{ext}"
    abs_path = os.path.join(folder, filename)
    with open(abs_path, "wb") as f:
        f.write(img_bytes)

    visitor.photo_rel_path = f"{visitor.cpf}/{filename}"  # para sua rota /uploads/<path:filename>
    db.session.commit()

'''



def create_visitor_if_not_exists_from_wizard() -> Visitor:
    w = session.get("wizard") or {}
    name = (w.get("name") or "").strip()
    father_name = (w.get("father_name") or "").strip()
    mom_name = (w.get("mom_name") or "").strip()
    cpf = (w.get("cpf") or "").strip()
    phone = (w.get("phone") or "").strip()
    email = w.get("email") or None
    empresa = (w.get("empresa") or "").strip()
    photo_rel_path = (w.get("photo_rel_path") or None)

    if not name or not cpf or not phone or not mom_name:
        raise ValueError("Cadastro incompleto (nome, cpf, telefone e nome da mãe).")

    existing = find_visitor_by_cpf(cpf)
    if existing:
        return existing

    visitor = Visitor(
        name=name,
        cpf=cpf,
        phone=phone,
        photo_rel_path=photo_rel_path,  # pode ser None
        email=email,
        empresa=empresa,
        father_name=father_name,
        mom_name=mom_name
    )
    db.session.add(visitor)
    db.session.commit()
    return visitor



def register_checkin(visitor: Visitor, destination: str) -> int:
    """
    Registra uma nova entrada (visita) para um visitante já cadastrado.
    """
    destination = (destination or "").strip()
    if not destination:
        raise ValueError("Informe o local/destino da visita.")

    visit = Visit(visitor_id=visitor.id, destination=destination, check_in=datetime.now())
    db.session.add(visit)
    db.session.commit()
    return visit.id

def checkout_visit(visit_id: int):
    """Registra saída para uma visita em aberto."""
    visit = db.session.get(Visit, visit_id)
    if not visit:
        raise ValueError("Visita não encontrada.")
    if visit.check_out is None:
        visit.check_out = datetime.now()  # UTC, tz-aware
        # em algum lugar do seu checkout
        visit.visitor.last_checkout_at = visit.check_out  # ← atualiza retenção
        db.session.commit()
    return visit
