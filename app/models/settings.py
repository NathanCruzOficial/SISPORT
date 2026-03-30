# =====================================================================
# models/settings.py
# Modelo e Helpers de Configurações da Aplicação — Define a tabela
# 'app_settings' (chave-valor) para armazenar configurações
# persistentes da aplicação (ex.: nome da portaria, limites, flags)
# e fornece funções utilitárias de leitura e escrita simplificadas.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from __future__ import annotations

from sqlalchemy import String, Text
from app.extensions import db


# =====================================================================
# Modelo — AppSetting (Configurações Chave-Valor)
# =====================================================================

class AppSetting(db.Model):
    """
    Armazena configurações da aplicação em formato chave-valor.

    Tabela: app_settings

    Colunas:
    - key   (String(64), PK):    Identificador único da configuração.
    - value (Text, NOT NULL):    Valor da configuração (texto livre).

    Exemplos de uso:
    - key='portaria_nome', value='Portaria Principal'
    - key='max_visitantes', value='50'
    """

    __tablename__ = "app_settings"

    key   = db.Column(String(64), primary_key=True)
    value = db.Column(Text, nullable=False)


# =====================================================================
# Helper — Leitura de Configuração
# =====================================================================

def get_setting(key: str, default: str | None = None) -> str | None:
    """
    Busca o valor de uma configuração pela chave.

    :param key:     (str) Chave da configuração a ser consultada.
    :param default: (str | None) Valor padrão caso a chave não exista
                    (padrão: None).
    :return: (str | None) Valor armazenado ou o default informado.
    """
    row = db.session.get(AppSetting, key)
    return row.value if row else default


# =====================================================================
# Helper — Escrita/Atualização de Configuração
# =====================================================================

def set_setting(key: str, value: str) -> None:
    """
    Cria ou atualiza uma configuração no banco.

    - Se a chave já existe, atualiza o valor (UPDATE).
    - Se não existe, insere um novo registro (INSERT).

    Nota: o chamador é responsável por executar db.session.commit()
    após a chamada para persistir a alteração.

    :param key:   (str) Chave da configuração.
    :param value: (str) Novo valor a ser armazenado.
    """
    row = db.session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.session.add(AppSetting(key=key, value=value))
