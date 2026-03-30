# =====================================================================
# report_services.py
# Módulo de Consultas de Visitas — Fornece funções utilitárias para
# consultar registros de visitas (Visit) filtrados por período,
# utilizados principalmente pelo dashboard e relatórios diários.
# =====================================================================

# ─────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────
from datetime import datetime, date, time
from ..models.visitor import Visit
from ..extensions import db


# =====================================================================
# Função Auxiliar — Intervalo de Início e Fim do Dia
# =====================================================================

def _day_range(d: date):
    """
    Calcula o intervalo completo de um dia (00:00:00.000000 até
    23:59:59.999999) para uso em filtros de consulta por data.

    :param d: (date) Data de referência.
    :return: (tuple[datetime, datetime]) Tupla com datetime de início
             e fim do dia informado.
    """
    start = datetime.combine(d, time.min)
    end = datetime.combine(d, time.max)
    return start, end


# =====================================================================
# Função — Consulta de Visitas por Dia
# =====================================================================

def get_visits_for_day(d: date):
    """
    Retorna todas as visitas registradas em um determinado dia,
    ordenadas por horário de entrada (check_in) ascendente.

    :param d: (date) Data para filtrar as visitas.
    :return: (list[Visit]) Lista de objetos Visit do dia, ordenados
             por check_in (mais antigo primeiro).
    """
    start, end = _day_range(d)
    return (
        db.session.query(Visit)
        .filter(Visit.check_in >= start, Visit.check_in <= end)
        .order_by(Visit.check_in.asc())
        .all()
    )
