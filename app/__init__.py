import os
from flask import Flask
from .config import Config
from .extensions import db

# Cria e configura a aplicação Flask (factory pattern).
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Garante que a pasta de uploads existe.
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Inicializa extensões.
    db.init_app(app)

    # Registra rotas (blueprints/views).
    from .views.visitor_views import visitor_bp
    from .views.admin_settings import admin_bp
    app.register_blueprint(visitor_bp)
    app.register_blueprint(admin_bp)

    # Cria as tabelas ao subir (para ambiente local simples).
    with app.app_context():
        from .models import visitor  # noqa: F401 (importa modelos)
        db.create_all()

    return app
