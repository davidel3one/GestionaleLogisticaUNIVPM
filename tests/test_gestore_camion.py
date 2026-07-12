from datetime import datetime

from gestionale_logistica.database.models import Camion
from gestionale_logistica.risorse.gestore_camion import GestoreCamion


def test_inserisci_camion(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.inserisci_camion(
        "C1", "AB123CD", "Furgone", datetime(2020, 1, 1), peso_massimo=100.0, volume_massimo=5.0
    )

    assert risultato.ok
    assert risultato.camion_id == "C1"
    with session_factory() as session:
        mezzo = session.get(Camion, "C1")
        assert mezzo.targa == "AB123CD"
        assert mezzo.tipo_mezzo == "Furgone"
        assert mezzo.flg_attivo is True
        assert mezzo.flg_sponda_idraulica is False
        assert mezzo.data_dismissione is None


def test_inserisci_camion_id_duplicato_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.inserisci_camion("C1", "XY999ZZ", "Camion", datetime(2021, 1, 1), 200.0, 10.0)

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_inserisci_camion_targa_duplicata_rifiutata(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.inserisci_camion("C2", "AB123CD", "Camion", datetime(2021, 1, 1), 200.0, 10.0)

    assert not risultato.ok
    assert "Targa" in risultato.motivo
    with session_factory() as session:
        assert session.get(Camion, "C2") is None


def test_modifica_camion_aggiunge_sponda_idraulica(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.modifica_camion("C1", flg_sponda_idraulica=True)

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Camion, "C1").flg_sponda_idraulica is True


def test_modifica_camion_targa_duplicata_rifiutata(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Camion", datetime(2021, 1, 1), 200.0, 10.0)

    risultato = gestore.modifica_camion("C2", targa="AB123CD")

    assert not risultato.ok
    assert "Targa" in risultato.motivo
    with session_factory() as session:
        assert session.get(Camion, "C2").targa == "XY999ZZ"


def test_modifica_camion_non_espone_un_parametro_id(session_factory):
    import inspect

    parametri = inspect.signature(GestoreCamion.modifica_camion).parameters
    assert "id" not in parametri


def test_modifica_camion_inesistente_rifiutata(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.modifica_camion("INESISTENTE", tipo_mezzo="X")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_disattiva_camion(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.disattiva_camion("C1", datetime(2026, 7, 20))

    assert risultato.ok
    with session_factory() as session:
        mezzo = session.get(Camion, "C1")
        assert mezzo.flg_attivo is False
        assert mezzo.data_dismissione == datetime(2026, 7, 20)
        assert mezzo is not None


def test_disattiva_camion_gia_fuori_servizio_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.disattiva_camion("C1")

    risultato = gestore.disattiva_camion("C1")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_disattiva_camion_inesistente_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.disattiva_camion("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo
