# =====================================================================
# models/visitor.py
# Modelos de Visitante e Visita — Define as tabelas 'visitors'
# (cadastro único de visitantes) e 'visits' (registros de entrada e
# saída). Juntas formam o núcleo do controle de portaria: cada
# visitante possui um cadastro permanente e pode ter múltiplas
# visitas associadas ao longo do tempo.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from datetime import datetime
from ..extensions import db


# =====================================================================
# Modelo — Visitor (Cadastro Único de Visitantes)
# =====================================================================

class Visitor(db.Model):
    """
    Cadastro permanente de um visitante na portaria.

    Tabela: visitors

    Colunas:
    - id               (Integer, PK):          Identificador auto-incremento.
    - name             (String(220), NOT NULL): Nome completo do visitante.
    - father_name      (String(220), NULL):     Nome do pai (opcional).
    - mom_name         (String(220), NOT NULL): Nome da mãe (obrigatório).
    - cpf              (String(16), UNIQUE):    CPF do visitante (índice único).
    - phone            (String(20), NOT NULL):  Telefone de contato.
    - email            (String(254), UNIQUE):   E-mail (opcional, porém único se informado).
    - empresa          (String(120), NULL):     Empresa do visitante (opcional).
    - photo_rel_path   (String(500), NULL):     Caminho relativo da foto armazenada.
    - last_checkout_at (DateTime, NULL, IDX):   Data/hora da última saída registrada
                                                (usado para política de retenção de dados).

    Relacionamentos:
    - visits: Lista de objetos Visit (1:N) — todas as visitas do visitante.
    """

    __tablename__ = "visitors"

    # ── Identificação ────────────────────────────────────────────────
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(220), nullable=False)

    # ── Filiação ─────────────────────────────────────────────────────
    father_name = db.Column(db.String(220), nullable=True)    # opcional
    mom_name    = db.Column(db.String(220), nullable=False)   # obrigatório

    # ── Documentos e Contato ─────────────────────────────────────────
    cpf   = db.Column(db.String(16),  nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20),  nullable=False)
    email = db.Column(db.String(254), nullable=True,  unique=True, index=True)

    # ── Empresa (opcional) ───────────────────────────────────────────
    empresa = db.Column(db.String(120), nullable=True)

    # ── Foto ─────────────────────────────────────────────────────────
    photo_rel_path = db.Column(db.String(500), nullable=True)

    # ── Relacionamento 1:N com Visit ─────────────────────────────────
    visits = db.relationship("Visit", back_populates="visitor", lazy=True)

    # ── Controle de Retenção ─────────────────────────────────────────
    last_checkout_at = db.Column(db.DateTime, nullable=True, index=True)


# =====================================================================
# Modelo — Visit (Registro de Entrada/Saída)
# =====================================================================

class Visit(db.Model):
    """
    Registro individual de uma visita (entrada e saída).

    Tabela: visits

    Cada visita representa um evento de acesso à portaria: o visitante
    entra (check_in) e, ao sair, o operador registra a saída (check_out).
    Enquanto check_out for NULL, a visita é considerada "em aberto".

    Colunas:
    - id          (Integer, PK):          Identificador auto-incremento.
    - visitor_id  (Integer, FK → visitors.id): Referência ao visitante.
    - destination (String(180), NOT NULL): Destino/setor da visita.
    - check_in    (DateTime, NOT NULL):   Data/hora de entrada (default: agora).
    - check_out   (DateTime, NULL):       Data/hora de saída (NULL = em aberto).

    Relacionamentos:
    - visitor: Objeto Visitor (N:1) — cadastro do visitante associado.
    """

    __tablename__ = "visits"

    # ── Identificação ────────────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── FK → Visitante ───────────────────────────────────────────────
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False)
    visitor    = db.relationship("Visitor", back_populates="visits")

    # ── Dados da Visita ──────────────────────────────────────────────
    destination = db.Column(db.String(180), nullable=False)

    # ── Controle de Entrada/Saída ────────────────────────────────────
    check_in  = db.Column(db.DateTime, default=datetime.now, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)

    # ─────────────────────────────────────────────────────────────────
    # Método — Verificação de Visita em Aberto
    # ─────────────────────────────────────────────────────────────────

    def is_open(self) -> bool:
        """
        Indica se a visita está em aberto (sem registro de saída).

        :return: (bool) True se check_out é None, False caso contrário.
        """
        return self.check_out is None
