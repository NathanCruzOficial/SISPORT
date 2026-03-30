# =====================================================================
# extensions.py
# Extensões da Aplicação Flask — Centraliza a criação de instâncias
# de extensões (SQLAlchemy, etc.) para evitar imports circulares.
# As instâncias são criadas aqui sem vínculo a um app específico e
# posteriormente inicializadas via init_app() na factory da aplicação.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from flask_sqlalchemy import SQLAlchemy


# =====================================================================
# Extensão — SQLAlchemy (ORM / Banco de Dados)
# =====================================================================

# Instância global do SQLAlchemy, utilizada por todos os modelos da
# aplicação (Visitor, Visit, AppSetting, User, etc.).
#
# Padrão Application Factory:
#   A instância é criada sem app vinculado. Na factory (create_app),
#   chama-se db.init_app(app) para conectar ao banco configurado.
#
# Uso nos modelos:
#   from app.extensions import db
#   class MeuModelo(db.Model): ...

db = SQLAlchemy()
