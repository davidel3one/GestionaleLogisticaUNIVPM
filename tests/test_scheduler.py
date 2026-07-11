import configparser
from datetime import timedelta

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
