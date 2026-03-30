# =====================================================================
# controllers/report_controller.py
# Controller de Relatório Diário — Camada intermediária entre a rota
# (blueprint) e o serviço de relatórios. Responsável por orquestrar
# a geração do relatório de visitas de um dia específico, delegando
# a consulta ao report_service.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from datetime import date
from ..services.report_service import get_visits_for_day


# =====================================================================
# Controller — Relatório Diário de Visitas
# =====================================================================

def day_report(d: date):
    """
    Gera os dados do relatório diário de visitas para exibição ou
    impressão.

    Delega a consulta ao serviço `report_service.get_visits_for_day`,
    que retorna todas as visitas (check-in e check-out) registradas
    na data informada.

    :param d: (date) Data do relatório desejado.
    :return:  Lista de visitas do dia (estrutura definida pelo serviço).
    """
    return get_visits_for_day(d)
