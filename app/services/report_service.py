from datetime import datetime, date, time
from ..models.visitor import Visit
from ..extensions import db

# Retorna início e fim do dia para filtrar visitas.
def _day_range(d: date):
    start = datetime.combine(d, time.min)
    end = datetime.combine(d, time.max)
    return start, end

# Busca todas as visitas do dia.
def get_visits_for_day(d: date):
    """
    Retorna lista de visitas do dia (ordenadas por entrada).
    """
    start, end = _day_range(d)
    return (
        db.session.query(Visit)
        .filter(Visit.check_in >= start, Visit.check_in <= end)
        .order_by(Visit.check_in.asc())
        .all()
    )
