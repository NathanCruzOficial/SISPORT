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
    - id               (Integer, PK):            Identificador auto-incremento.
    - name             (String(220), NOT NULL):  Nome completo do visitante.
    - category_id      (Integer, FK):            Categoria do visitante.
    - father_name      (String(220), NULL):      Nome do pai.
    - mom_name         (String(220), NOT NULL):  Nome da mãe.
    - cpf              (String(16), UNIQUE):     CPF do visitante.
    - phone            (String(20), NOT NULL):   Telefone de contato.
    - email            (String(254), UNIQUE):    E-mail opcional.
    - empresa          (String(120), NULL):      Empresa do visitante.
    - photo_data       (LargeBinary, NULL):      Bytes da foto de perfil.
    - photo_mimetype   (String(32), NULL):       Mimetype da foto.
    - last_checkout_at (DateTime, NULL, IDX):    Data/hora da última saída.

    Relacionamentos:
    - category: Categoria do visitante.
    - visits: Lista de objetos Visit vinculados ao visitante.
    """

    __tablename__ = "visitors"

    # ── Identificação ────────────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(220), nullable=False)

    # ── Categoria ────────────────────────────────────────────────────
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("visitor_categories.id"),
        nullable=True,
        index=True,
    )

    category = db.relationship(
        "VisitorCategory",
        backref="visitors",
        lazy="joined",
    )

    # ── Filiação ─────────────────────────────────────────────────────
    father_name = db.Column(db.String(220), nullable=True)
    mom_name = db.Column(db.String(220), nullable=False)

    # ── Documentos e Contato ─────────────────────────────────────────
    cpf = db.Column(db.String(16), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(254), nullable=True, unique=True, index=True)

    # ── Empresa ──────────────────────────────────────────────────────
    empresa = db.Column(db.String(120), nullable=True)

    # ── Foto ─────────────────────────────────────────────────────────
    photo_data = db.Column(db.LargeBinary, nullable=True)
    photo_mimetype = db.Column(db.String(32), nullable=True)

    # ── Relacionamento 1:N com Visit ─────────────────────────────────
    visits = db.relationship(
        "Visit",
        back_populates="visitor",
        lazy=True,
    )

    # ── Controle de Retenção ─────────────────────────────────────────
    last_checkout_at = db.Column(db.DateTime, nullable=True, index=True)

    # ── Helpers opcionais para templates/exportações ─────────────────
    @property
    def category_value(self):
        """
        Slug/value da categoria, ex: civil, militar, visitante_externo.
        """
        return self.category.value if self.category else None

    @property
    def category_label(self):
        """
        Nome exibível da categoria.
        """
        return self.category.label if self.category else None


# =====================================================================
# Modelo — Visit (Registro de Entrada/Saída)
# =====================================================================

class Visit(db.Model):
    """
    Registro individual de uma visita.

    Tabela: visits

    Cada visita representa um evento de acesso à portaria: o visitante
    entra e, ao sair, o operador registra a saída. Enquanto check_out
    for NULL, a visita é considerada em aberto.
    """

    __tablename__ = "visits"

    # ── Identificação ────────────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── FK → Visitante ───────────────────────────────────────────────
    visitor_id = db.Column(
        db.Integer,
        db.ForeignKey("visitors.id"),
        nullable=False,
    )

    visitor = db.relationship(
        "Visitor",
        back_populates="visits",
    )

    # ── Dados da Visita ──────────────────────────────────────────────
    destination = db.Column(db.String(255), nullable=False)

    # ── Motivo da visita ─────────────────────────────────────────────
    reason = db.Column(db.Text, nullable=True)

    # ── Controle de Entrada/Saída ────────────────────────────────────
    check_in = db.Column(db.DateTime, default=datetime.now, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)

    def is_open(self) -> bool:
        """
        Indica se a visita está em aberto.
        """
        return self.check_out is None


# =====================================================================
# Modelo — TempPhoto
# =====================================================================

class TempPhoto(db.Model):
    """
    Foto temporária do wizard.

    Evita armazenar BLOB grande no cookie de sessão.
    """

    __tablename__ = "temp_photos"

    id = db.Column(db.String(64), primary_key=True)
    photo_data = db.Column(db.LargeBinary)
    photo_mimetype = db.Column(db.String(32), default="image/jpeg")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
