from datetime import date
from ..services.report_service import get_visits_for_day

# Gera os dados do relatório diário.
def day_report(d: date):
    """
    Retorna a lista de visitas do dia para exibição/impressão.
    """
    return get_visits_for_day(d)
