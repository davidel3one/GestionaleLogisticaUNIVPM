from datetime import datetime

from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra
from gestionale_logistica.risorse.gestore_squadre import GestoreSquadre


def inserisci_camion(session, id_="CAM1", flg_attivo=True):
    session.add(
        Camion(
            id=id_, targa=f"TARGA-{id_}", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
            flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
            flg_attivo=flg_attivo,
        )
    )


def inserisci_dipendente(session, id_, flg_attivo=True):
    session.add(
        Dipendente(
            id=id_, nome="Mario", cognome="Rossi", codice_fiscale=f"CF-{id_}",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=flg_attivo, flg_certificazione_gas=False,
        )
    )


def test_crea_squadra(session_factory):
    gestore = GestoreSquadre(session_factory)

    risultato = gestore.crea_squadra("SQ1", datetime(2026, 1, 1))

    assert risultato.ok
    assert risultato.squadra_id == "SQ1"
    with session_factory() as session:
        sq = session.get(Squadra, "SQ1")
        assert sq.flg_attiva is True
        assert sq.data_creazione == datetime(2026, 1, 1)


def test_crea_squadra_id_duplicato_rifiutato(session_factory):
    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.crea_squadra("SQ1")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_apri_composizione(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2", datetime(2026, 1, 1))

    assert risultato.ok
    assert risultato.composizione_id == "C1"
    with session_factory() as session:
        comp = session.get(ComposizioneSquadra, "C1")
        assert comp.squadra_id == "SQ1"
        assert comp.camion_id == "CAM1"
        assert comp.dipendente_1_id == "D1"
        assert comp.dipendente_2_id == "D2"
        assert comp.data_inizio_validita == datetime(2026, 1, 1)
        assert comp.data_fine_validita is None
        assert comp.flg_attiva is True


def test_apri_composizione_id_duplicato_rifiutato(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")
    gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_apri_composizione_squadra_inesistente_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)

    risultato = gestore.apri_composizione("C1", "SQ-INESISTENTE", "CAM1", "D1", "D2")

    assert not risultato.ok
    assert "non trovata" in risultato.motivo


def test_apri_composizione_squadra_non_attiva_rifiutata(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=False, data_creazione=datetime(2020, 1, 1)))
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2")

    assert not risultato.ok
    assert "non attiva" in risultato.motivo


def test_apri_composizione_camion_inesistente_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM-INESISTENTE", "D1", "D2")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_apri_composizione_camion_non_attivo_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_camion(session, flg_attivo=False)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2")

    assert not risultato.ok
    assert "servizio" in risultato.motivo


def test_apri_composizione_dipendenti_uguali_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D1")

    assert not risultato.ok
    assert "distinti" in risultato.motivo


def test_apri_composizione_dipendente_inesistente_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D-INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_apri_composizione_dipendente_non_attivo_rifiutata(session_factory):
    with session_factory() as session:
        inserisci_camion(session)
        inserisci_dipendente(session, "D1")
        inserisci_dipendente(session, "D2", flg_attivo=False)
        session.commit()

    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("SQ1")

    risultato = gestore.apri_composizione("C1", "SQ1", "CAM1", "D1", "D2")

    assert not risultato.ok
    assert "servizio" in risultato.motivo
