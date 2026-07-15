from datetime import date, datetime, timedelta

from gestionale_logistica.database.enums import StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import CausaleFallimento, EsitoConsegna, RegistroEsiti, Squadra, Viaggio
from gestionale_logistica.gui.components import IconChipVariant
from gestionale_logistica.gui.dashboard.dashboard_data import (
    carica_attivita_recente,
    carica_kpi_dashboard,
    carica_pianificazione_prossimi_giorni,
)
from test_logistica import crea_flotta_semplice, crea_ordine


def _crea_viaggio(session, comp_id, viaggio_id, stato, data_partenza):
    session.add(
        Viaggio(
            id=viaggio_id,
            data_partenza_prevista=data_partenza,
            data_arrivo_prevista=data_partenza + timedelta(hours=8),
            data_creazione=data_partenza,
            km_percorsi=None,
            stato_viaggio=stato,
            composizione_id=comp_id,
        )
    )


def _crea_esito(session, ordine_id, viaggio_id, stato, quando, registro_id, causale_id=None):
    session.add(
        EsitoConsegna(
            stato_esito=stato,
            data_registrazione=quando,
            ordine_id=ordine_id,
            viaggio_id=viaggio_id,
            causale_id=causale_id,
            registro_id=registro_id,
        )
    )


# --- KPI: conteggi ordini per stato ---


def test_kpi_conta_ordini_ricevuti_e_in_consegna(session_factory):
    with session_factory() as session:
        for i in range(3):
            session.add(crea_ordine(f"RIC-{i}"))
        for i in range(2):
            ordine = crea_ordine(f"CON-{i}")
            ordine.stato_ordine = StatoOrdine.IN_CONSEGNA
            session.add(ordine)
        completato = crea_ordine("COMP-1")
        completato.stato_ordine = StatoOrdine.COMPLETATO
        session.add(completato)
        session.commit()

    kpi = carica_kpi_dashboard(session_factory)
    assert kpi.ordini_ricevuti == 3
    assert kpi.ordini_in_consegna == 2


# --- KPI: disponibilita' dipendenti/camion ---


def test_kpi_disponibilita_esclude_solo_chi_e_su_viaggio_in_corso(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        crea_flotta_semplice(session, "C2")
        crea_flotta_semplice(session, "C3")
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, datetime(2026, 7, 10, 8, 0))
        _crea_viaggio(session, "C2", "V2", StatoViaggio.PIANIFICATO, datetime(2026, 7, 20, 8, 0))
        session.commit()

    kpi = carica_kpi_dashboard(session_factory, ora_riferimento=datetime(2026, 7, 10, 10, 0))
    assert kpi.dipendenti_totali == 6
    assert kpi.dipendenti_disponibili == 4
    assert kpi.camion_totali == 3
    assert kpi.camion_disponibili == 2


# --- KPI: trend consegnati/falliti ---


def test_kpi_trend_percentuale_consegnati(session_factory):
    oggi = datetime(2026, 7, 15, 12, 0)
    ieri = oggi - timedelta(days=1)
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(RegistroEsiti(id=1, data_riferimento=datetime(2026, 7, 15)))
        session.add(RegistroEsiti(id=2, data_riferimento=datetime(2026, 7, 14)))
        for i in range(4):
            session.add(crea_ordine(f"OGGI-{i}"))
        for i in range(2):
            session.add(crea_ordine(f"IERI-{i}"))
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, oggi)
        session.commit()
        for i in range(4):
            _crea_esito(session, f"OGGI-{i}", "V1", StatoEsito.COMPLETATO, oggi, registro_id=1)
        for i in range(2):
            _crea_esito(session, f"IERI-{i}", "V1", StatoEsito.COMPLETATO, ieri, registro_id=2)
        session.commit()

    kpi = carica_kpi_dashboard(session_factory, ora_riferimento=oggi)
    assert kpi.ordini_consegnati_oggi == 4
    assert kpi.trend_consegnati == "↑ 100% vs ieri"


def test_kpi_trend_none_quando_ieri_zero(session_factory):
    oggi = datetime(2026, 7, 15, 12, 0)
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(RegistroEsiti(id=1, data_riferimento=datetime(2026, 7, 15)))
        session.add(crea_ordine("O1"))
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, oggi)
        session.commit()
        _crea_esito(session, "O1", "V1", StatoEsito.COMPLETATO, oggi, registro_id=1)
        session.commit()

    kpi = carica_kpi_dashboard(session_factory, ora_riferimento=oggi)
    assert kpi.ordini_consegnati_oggi == 1
    assert kpi.trend_consegnati is None


def test_kpi_trend_assoluto_falliti(session_factory):
    oggi = datetime(2026, 7, 15, 12, 0)
    ieri = oggi - timedelta(days=1)
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(CausaleFallimento(codice="X", descrizione="Motivo"))
        session.add(RegistroEsiti(id=1, data_riferimento=datetime(2026, 7, 15)))
        session.add(RegistroEsiti(id=2, data_riferimento=datetime(2026, 7, 14)))
        session.add(crea_ordine("F-OGGI-1"))
        session.add(crea_ordine("F-OGGI-2"))
        session.add(crea_ordine("F-IERI-1"))
        _crea_viaggio(session, "C1", "V1", StatoViaggio.IN_CORSO, oggi)
        session.commit()
        _crea_esito(session, "F-OGGI-1", "V1", StatoEsito.FALLITO, oggi, registro_id=1, causale_id="X")
        _crea_esito(session, "F-OGGI-2", "V1", StatoEsito.FALLITO, oggi, registro_id=1, causale_id="X")
        _crea_esito(session, "F-IERI-1", "V1", StatoEsito.FALLITO, ieri, registro_id=2, causale_id="X")
        session.commit()

    kpi = carica_kpi_dashboard(session_factory, ora_riferimento=oggi)
    assert kpi.ordini_falliti_oggi == 2
    assert kpi.trend_falliti == "↑ 1 vs ieri"


# --- Pianificazione prossimi giorni ---


def test_pianificazione_conta_solo_viaggi_pianificati_nel_range(session_factory):
    oggi = date(2026, 7, 15)
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        crea_flotta_semplice(session, "C2")
        crea_flotta_semplice(session, "C3")
        _crea_viaggio(session, "C1", "V1", StatoViaggio.PIANIFICATO, datetime(2026, 7, 16, 9, 0))
        _crea_viaggio(session, "C2", "V2", StatoViaggio.PIANIFICATO, datetime(2026, 7, 16, 14, 0))
        _crea_viaggio(session, "C3", "V3", StatoViaggio.IN_CORSO, datetime(2026, 7, 16, 9, 0))
        session.commit()

    giorni = carica_pianificazione_prossimi_giorni(session_factory, giorni=3, oggi=oggi)
    assert len(giorni) == 3
    assert giorni[0].label == "Mer 15"
    assert giorni[0].numero_viaggi == 0
    assert giorni[1].label == "Gio 16"
    assert giorni[1].numero_viaggi == 2


# --- Attivita' recente ---


def test_attivita_recente_ordina_per_timestamp_decrescente_e_rispetta_limite(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="S1", flg_attiva=True, data_creazione=datetime(2026, 7, 10, 8, 0)))
        session.add(Squadra(id="S2", flg_attiva=True, data_creazione=datetime(2026, 7, 12, 8, 0)))
        session.commit()

    voci = carica_attivita_recente(session_factory, limite=1)
    assert len(voci) == 1
    assert "S2" in voci[0].testo
    assert voci[0].variant == IconChipVariant.BLUE
