import configparser
from datetime import timedelta

import pytest
from apscheduler.triggers.cron import CronTrigger

from gestionale_logistica.scheduler import avvia_scheduler


def crea_config(intervallo_minuti="5", report_orario="21:00"):
    config = configparser.ConfigParser()
    config.read_dict(
        {
            "scheduler": {
                "verifica_partenza_intervallo_minuti": intervallo_minuti,
                "report_orario": report_orario,
            }
        }
    )
    return config


def test_registra_job_rf14_con_intervallo_da_config():
    scheduler = avvia_scheduler(crea_config(intervallo_minuti="7"))
    try:
        job = scheduler.get_job("rf14_verifica_partenza")
        assert job is not None
        assert job.trigger.interval == timedelta(minutes=7)
    finally:
        scheduler.shutdown()


def test_registra_job_rf19_con_orario_da_config():
    scheduler = avvia_scheduler(crea_config(report_orario="22:30"))
    try:
        job = scheduler.get_job("rf19_report_giornaliero")
        assert job is not None
        assert str(job.trigger) == str(CronTrigger(hour=22, minute=30))
    finally:
        scheduler.shutdown()


def test_scheduler_avviato_e_usa_fallback_se_config_incompleta():
    scheduler = avvia_scheduler(configparser.ConfigParser())
    try:
        assert scheduler.running
        assert scheduler.get_job("rf14_verifica_partenza").trigger.interval == timedelta(minutes=5)
        assert str(scheduler.get_job("rf19_report_giornaliero").trigger) == str(CronTrigger(hour=21, minute=0))
    finally:
        scheduler.shutdown()


@pytest.mark.parametrize("report_orario", ["21", "21:00:00", "25:00", "21:99", "ventuno:00", ""])
def test_avvia_scheduler_rifiuta_report_orario_malformato_con_errore_leggibile(report_orario):
    # config.getint/get con fallback copre solo la chiave assente, non un valore presente ma
    # malformato: senza validazione esplicita, un valore come "21" (senza minuti) produce un
    # generico "ValueError: not enough values to unpack" invece di un messaggio comprensibile.
    with pytest.raises(ValueError, match="report_orario"):
        avvia_scheduler(crea_config(report_orario=report_orario))


@pytest.mark.parametrize("intervallo_minuti", ["0", "-5", "abc", ""])
def test_avvia_scheduler_rifiuta_intervallo_minuti_non_valido_con_errore_leggibile(intervallo_minuti):
    # APScheduler non convalida IntervalTrigger: minutes=0 diventa silenziosamente un intervallo
    # di 1 secondo (verifica_partenze() interrogherebbe il DB ogni secondo all'infinito) e
    # minutes negativo un intervallo dal comportamento non documentato - nessuno dei due casi
    # solleva un errore da solo, quindi va convalidato esplicitamente prima di arrivare li'.
    with pytest.raises(ValueError, match="verifica_partenza_intervallo_minuti"):
        avvia_scheduler(crea_config(intervallo_minuti=intervallo_minuti))
