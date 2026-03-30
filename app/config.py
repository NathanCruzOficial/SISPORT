# =====================================================================
# app/config.py
# Configurações do Flask — Define as configurações centrais da
# aplicação Flask (banco de dados, sessão e uploads). Os caminhos
# de diretórios são importados do módulo paths.py, mantendo aqui
# apenas parâmetros específicos do framework.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
import os
from app.paths import db_path, UPLOADS_DIR


# =====================================================================
# Classe — Configuração Principal do Flask
# =====================================================================

class Config:
    """
    Configuração centralizada da aplicação Flask.

    Atributos:
    - SQLALCHEMY_DATABASE_URI (str):           URI de conexão SQLite
                                               (caminho resolvido por paths.db_path).
    - SQLALCHEMY_TRACK_MODIFICATIONS (bool):   Desativado para evitar overhead
                                               de rastreamento de alterações.
    - SECRET_KEY (str):                        Chave secreta para assinatura de
                                               sessão (via variável de ambiente
                                               SECRET_KEY ou fallback local).
    - UPLOAD_FOLDER (str):                     Diretório de uploads de fotos
                                               (resolvido por paths.UPLOADS_DIR).
    """

    # ── Banco de Dados SQLite ────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Sessão Flask ─────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "sisport-local-dev-key")

    # ── Uploads (mesmo diretório gerenciado por paths.py) ────────────
    UPLOAD_FOLDER = str(UPLOADS_DIR)
