from datetime import datetime
from ..extensions import db

class Visitor(db.Model):
    """Tabela de cadastro único de visitantes."""
    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(16), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=True)  # <-- NOVO

    # Caminho relativo em uploads/<cpf>/foto.jpg (ou timestamp, se preferir).
    photo_rel_path = db.Column(db.String(500), nullable=False)

    visits = db.relationship("Visit", back_populates="visitor", lazy=True)


class Visit(db.Model):
    """Tabela de registros de entrada/saída (cada visita é um evento)."""
    __tablename__ = "visits"

    id = db.Column(db.Integer, primary_key=True)

    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False)
    visitor = db.relationship("Visitor", back_populates="visits")

    destination = db.Column(db.String(180), nullable=False)

    check_in = db.Column(db.DateTime, default=datetime.now, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)

    def is_open(self) -> bool:
        """Indica se a visita está em aberto (sem saída)."""
        return self.check_out is None
