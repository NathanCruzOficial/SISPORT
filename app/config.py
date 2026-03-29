"""
app/config.py — Configurações do Flask
========================================
Caminhos vêm do paths.py. Aqui só tem config do Flask.
"""

import os
from app.paths import db_path, UPLOADS_DIR


class Config:
    # Banco SQLite
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessão
    SECRET_KEY = os.environ.get("SECRET_KEY", "sisport-local-dev-key")

    # Uploads — mesma pasta que o paths.py gerencia
    UPLOAD_FOLDER = str(UPLOADS_DIR)
