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
from flask import Flask, request, send_from_directory, url_for
from .config import Config
from .extensions import db, migrate
from app.paths import ensure_app_dirs
from app.version import __version__, APP_NAME
from time import time


# =====================================================================
# Função Auxiliar — Garantir colunas novas em banco legado
# =====================================================================

def _ensure_photo_columns():
    """
    Adiciona as colunas photo_data e photo_mimetype na tabela visitors
    caso ainda não existam (banco legado criado antes dessa feature).

    O SQLAlchemy db.create_all() NÃO altera tabelas já existentes —
    ele só cria tabelas novas. Por isso, quando adicionamos colunas
    no model de uma tabela que já existe no .sqlite3, precisamos
    fazer ALTER TABLE manualmente.

    Esta função:
    1. Inspeciona as colunas atuais da tabela 'visitors'.
    2. Se 'photo_data' não existir, adiciona como BLOB.
    3. Se 'photo_mimetype' não existir, adiciona como VARCHAR(32).

    É segura para rodar múltiplas vezes — se as colunas já existirem,
    simplesmente não faz nada.

    :return: None
    """
    from sqlalchemy import text, inspect

    inspector = inspect(db.engine)

    # Verifica se a tabela visitors existe (banco novo = create_all já criou)
    if "visitors" not in inspector.get_table_names():
        return

    columns = [col["name"] for col in inspector.get_columns("visitors")]

    with db.engine.begin() as conn:
        if "photo_data" not in columns:
            conn.execute(text("ALTER TABLE visitors ADD COLUMN photo_data BLOB"))

        if "photo_mimetype" not in columns:
            conn.execute(text(
                "ALTER TABLE visitors ADD COLUMN photo_mimetype VARCHAR(32)"
            ))


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
    6. Garante que colunas novas (photo_data, photo_mimetype) existam
       em bancos legados via _ensure_photo_columns().
    7. Executa migração automática de fotos do disco para o banco.

    :return: (Flask) Instância configurada e pronta para uso.
    """
    # Cria todas as pastas do sistema (db, uploads, logs, etc.)
    ensure_app_dirs()

    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)


    # Registra blueprints
    from .views.visitor_views import visitor_bp
    from .views.admin_settings import admin_bp
    app.register_blueprint(visitor_bp, url_prefix="/")
    app.register_blueprint(admin_bp)


    @app.context_processor
    def inject_globals():
        return dict(
            app_version=__version__,
            app_name=APP_NAME,
        )

    
    @app.context_processor
    def inject_open_count():
        from .models.visitor import Visit
        count = Visit.query.filter_by(check_out=None).count()
        return dict(open_count=count)
    
    @app.after_request
    def cache_static_assets(response):
        """Cache agressivo para modelos e face-api.js"""
        path = request.path
        if path.startswith("/static/models/") or path.endswith("face-api.min.js"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    
    @app.route('/icone.ico')
    def favicon():
        return send_from_directory(app.root_path, 'icone.ico', mimetype='image/x-icon')
    
    def photo_url(source, record_id):
        return (
            url_for("visitor.serve_photo", source=source, record_id=str(record_id))
            + f"?t={int(time())}"
        )

    app.jinja_env.globals["photo_url"] = photo_url

    # Importa todos os models para que SQLAlchemy/Alembic conheçam
    # as tabelas durante geração/aplicação das migrations.
    from . import models  # noqa: F401

    return app


    return app

