from datetime import datetime
from flask import session
from ..extensions import db
from ..models.visitor import Visitor, Visit
from ..services.photo_service import save_or_replace_profile_photo

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
        "photo_rel_path": "",
    }

def wizard_step1_submit(name: str, cpf: str):
    """Etapa 1: salva nome/CPF e vai para etapa 2."""
    w = session.get("wizard") or {}
    w.update({"name": (name or "").strip(), "cpf": (cpf or "").strip(), "step": 2})
    session["wizard"] = w

def wizard_step2_submit(photo_data_url: str):
    """Etapa 2: salva foto do cadastro (vinculada ao CPF) e vai para etapa 3."""
    w = session.get("wizard") or {}
    cpf = (w.get("cpf") or "").strip()
    if not cpf:
        raise ValueError("CPF não informado. Volte à etapa 1.")

    photo_rel_path = save_or_replace_profile_photo(photo_data_url, cpf)
    w.update({"photo_rel_path": photo_rel_path, "step": 3})
    session["wizard"] = w

def create_visitor_if_not_exists_from_wizard() -> Visitor:
    """
    Cria o cadastro do visitante caso não exista.
    Se já existir (condição de corrida/uso), retorna o existente.
    """
    w = session.get("wizard") or {}
    name = (w.get("name") or "").strip()
    cpf = (w.get("cpf") or "").strip()
    photo_rel_path = (w.get("photo_rel_path") or "").strip()

    if not name or not cpf or not photo_rel_path:
        raise ValueError("Cadastro incompleto (nome/cpf/foto).")

    existing = find_visitor_by_cpf(cpf)
    if existing:
        return existing

    visitor = Visitor(name=name, cpf=cpf, photo_rel_path=photo_rel_path)
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
        visit.check_out = datetime.now()
        db.session.commit()
    return visit
