# app/seed.py
"""
Popula a tabela ``settings`` com os valores padrão definidos em
``app.defaults``, caso ainda não existam no banco.

Utiliza ``_next_id()`` para calcular o ID manualmente, garantindo
compatibilidade com bancos antigos cuja coluna ``id`` foi criada
sem AUTOINCREMENT.
"""

from app.defaults import DEFAULTS
from app.extensions import db
from app.models.settings import Setting, _next_id


def seed_defaults():
    """
    Percorre todas as chaves de ``DEFAULTS``.
    Se a chave não existir no banco, insere com o valor padrão.
    """
    existing_keys = {s.key for s in Setting.query.all()}

    added = 0
    for key, (default_value, _type) in DEFAULTS.items():
        if key not in existing_keys:
            row = Setting(id=_next_id() + added, key=key, value=default_value)
            db.session.add(row)
            added += 1

    if added:
        db.session.commit()
