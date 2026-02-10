import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class Config:
    # Configuração do SQLite local.
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Chave para sessão (wizard multi-etapas).
    SECRET_KEY = os.environ.get("SECRET_KEY", "cruz-local-dev-key")

    # Pasta para salvar fotos capturadas.
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
