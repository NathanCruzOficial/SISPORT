# app/models/settings.py
"""
Modelo e helpers para a tabela **settings** (configurações do sistema).

A tabela armazena pares chave/valor que controlam o comportamento do
SISPORT (nome da instituição, categorias de visitante, política de
retenção etc.).

Nota sobre compatibilidade
--------------------------
Bancos criados em versões anteriores podem não possuir AUTOINCREMENT
na coluna ``id``.  Como ``db.create_all()`` não altera tabelas já
existentes, o helper ``_next_id()`` calcula o próximo ID manualmente,
garantindo que inserções funcionem em **qualquer** versão do schema.
"""

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

    Necessário para manter compatibilidade com bancos antigos cuja
    coluna ``id`` foi criada sem AUTOINCREMENT.  Usa ``COALESCE``
    para retornar 0 caso a tabela esteja vazia.

    Returns:
        int: Próximo valor inteiro a ser usado como ``id``.
    """
    max_id = db.session.query(
        db.func.coalesce(db.func.max(Setting.id), 0)
    ).scalar()
    return max_id + 1


# ── API pública ───────────────────────────────────────────────────────

def get_setting(key: str, fallback: str | None = None) -> str:
    """
    Obtém o valor de uma configuração.

    Ordem de resolução:
        1. Valor persistido no banco (tabela ``settings``).
        2. ``fallback`` informado pelo chamador (se houver).
        3. Valor padrão definido em ``app.defaults``.

    Args:
        key:      Chave da configuração (ex.: ``'inst_name'``).
        fallback: Valor alternativo caso a chave não exista no banco.

    Returns:
        str: Valor da configuração.
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

    Se a chave já existir no banco, apenas atualiza o campo ``value``.
    Caso contrário, insere um novo registro com ID calculado por
    ``_next_id()`` (compatível com bancos sem AUTOINCREMENT).

    **Importante:** o chamador é responsável por executar
    ``db.session.commit()`` após a chamada.

    Args:
        key:   Chave da configuração.
        value: Novo valor a ser persistido.
    """
    row = Setting.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(Setting(id=_next_id(), key=key, value=value))
