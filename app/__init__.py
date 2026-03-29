"""
app/__init__.py — Factory da aplicação Flask
==============================================
"""

from flask import Flask
from .config import Config
from .extensions import db
from app.paths import ensure_app_dirs


def create_app() -> Flask:
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
