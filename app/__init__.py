# =====================================================================
# app/__init__.py
# Factory da Aplicação Flask — Responsável por criar e configurar a
# instância do Flask, inicializar extensões (SQLAlchemy), registrar
# blueprints (visitor, admin) e garantir a criação das tabelas e
# diretórios necessários para o funcionamento da aplicação.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from flask import Flask
from .config import Config
from .extensions import db
from app.paths import ensure_app_dirs


# =====================================================================
# Função — Factory de Criação da Aplicação
# =====================================================================

def create_app() -> Flask:
    """
    Application Factory do Flask. Executa a seguinte sequência:

    1. Garante a existência de todos os diretórios do sistema
       (banco, uploads, logs, etc.) via ensure_app_dirs().
    2. Cria a instância Flask e carrega as configurações de Config.
    3. Inicializa extensões (SQLAlchemy).
    4. Registra os blueprints de rotas (visitor_bp, admin_bp).
    5. Dentro do app_context, importa os models e cria as tabelas
       no banco de dados (db.create_all()).

    :return: (Flask) Instância configurada e pronta para uso.
    """
    # Cria todas as pastas do sistema (db, uploads, logs, etc.)
    ensure_app_dirs()

    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões
    db.init_app(app)

    # Registra blueprints
    from .views.visitor_views import visitor_bp
    from .views.admin_settings import admin_bp
    app.register_blueprint(visitor_bp)
    app.register_blueprint(admin_bp)

    # Cria tabelas
    with app.app_context():
        from .models import visitor  # noqa: F401
        db.create_all()

    return app
