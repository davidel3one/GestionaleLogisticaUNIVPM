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


def _parsa_orario_report(valore: str) -> tuple[int, int]:
    """Valida il formato HH:MM di [scheduler].report_orario. Il fallback di configparser copre
    solo la chiave assente in config.ini, non un valore presente ma malformato (es. "21" invece
    di "21:00") - senza questo controllo un valore simile solleva un generico "ValueError: not
    enough values to unpack" dentro avvia_scheduler(), chiamato in main() prima che la GUI si
    apra: l'app non parte, senza un messaggio comprensibile.
    """
    parti = valore.split(":")
    if len(parti) != 2 or not all(parte.isdigit() for parte in parti):
        raise ValueError(
            f"config.ini [scheduler].report_orario='{valore}' non valido: formato atteso HH:MM (es. 21:00)"
        )
    ora, minuti = int(parti[0]), int(parti[1])
    if not (0 <= ora <= 23 and 0 <= minuti <= 59):
        raise ValueError(
            f"config.ini [scheduler].report_orario='{valore}' non valido: ora deve essere 0-23, minuti 0-59"
        )
    return ora, minuti


def _parsa_intervallo_minuti(valore: str) -> int:
    """Valida che [scheduler].verifica_partenza_intervallo_minuti sia un intero positivo.
    APScheduler non lo convalida affatto: IntervalTrigger(minutes=0) diventa silenziosamente un
    intervallo di 1 secondo (non "mai"), e IntervalTrigger(minutes=N negativo) un intervallo
    negativo dal comportamento non documentato - in entrambi i casi lo scheduler partirebbe
    con un comportamento sbagliato senza sollevare alcun errore.
    """
    try:
        minuti = int(valore)
    except ValueError:
        raise ValueError(
            f"config.ini [scheduler].verifica_partenza_intervallo_minuti='{valore}' non valido: "
            "atteso un intero positivo"
        ) from None
    if minuti <= 0:
        raise ValueError(
            f"config.ini [scheduler].verifica_partenza_intervallo_minuti={minuti} non valido: "
            "deve essere un intero positivo"
        )
    return minuti


def avvia_scheduler(config: configparser.ConfigParser) -> BackgroundScheduler:
    """Avvia lo scheduler interno (RNF3/architettura) che gestisce i trigger automatici a
    orario: verifica partenza (RF14, ogni N minuti) e generazione report (RF19, un orario fisso
    al giorno). Entrambi gli intervalli vengono da config.ini [scheduler], gia' presente a
    prescindere da questa feature.
    """
    intervallo_minuti = _parsa_intervallo_minuti(
        config.get("scheduler", "verifica_partenza_intervallo_minuti", fallback="5")
    )
    ora, minuti = _parsa_orario_report(config.get("scheduler", "report_orario", fallback="21:00"))

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
