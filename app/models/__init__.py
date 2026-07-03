# =====================================================================
# app/models/__init__.py
# Centraliza a importação dos models para garantir que todos sejam
# registrados no metadata do SQLAlchemy e detectados pelo Flask-Migrate.
# =====================================================================

from .visitor import Visitor, Visit, TempPhoto  # noqa: F401
from .visitor_destination import VisitorDestinationGroup, VisitorDestinationPlace
from .settings import Setting  # noqa: F401
from .visitor_category import VisitorCategory

