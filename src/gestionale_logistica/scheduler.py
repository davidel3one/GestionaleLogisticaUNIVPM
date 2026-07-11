import configparser
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione

logger = logging.getLogger(__name__)


def _job_verifica_partenze() -> None:
    """RF14, invocato periodicamente dallo scheduler."""
    viaggi_avviati = GestoreLogistica().verifica_partenze()
    if viaggi_avviati:
        logger.info("Verifica partenza automatica: avviati %d viaggi %s", len(viaggi_avviati), viaggi_avviati)


def _job_report_giornaliero() -> None:
    """RF19, invocato ogni giorno all'orario configurato."""
    risultato = GestoreRendicontazione().genera_report_giornaliero()
    if risultato.generato:
        logger.info("Report consuntivo generato: %s", risultato.percorso_file)
    else:
        logger.info("Report consuntivo non generato: %s", risultato.motivo)


def avvia_scheduler(config: configparser.ConfigParser) -> BackgroundScheduler:
    """Avvia lo scheduler interno (RNF3/architettura) che gestisce i trigger automatici a
    orario: verifica partenza (RF14, ogni N minuti) e generazione report (RF19, un orario fisso
    al giorno). Entrambi gli intervalli vengono da config.ini [scheduler], gia' presente a
    prescindere da questa feature.
    """
    intervallo_minuti = config.getint("scheduler", "verifica_partenza_intervallo_minuti", fallback=5)
    ora, minuti = (int(parte) for parte in config.get("scheduler", "report_orario", fallback="21:00").split(":"))

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _job_verifica_partenze,
        IntervalTrigger(minutes=intervallo_minuti),
        id="rf14_verifica_partenza",
    )
    scheduler.add_job(
        _job_report_giornaliero,
        CronTrigger(hour=ora, minute=minuti),
        id="rf19_report_giornaliero",
    )
    scheduler.start()
    return scheduler
