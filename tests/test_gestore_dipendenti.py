from datetime import datetime

from gestionale_logistica.database.models import Dipendente
from gestionale_logistica.risorse.gestore_dipendenti import GestoreDipendenti


def test_inserisci_dipendente(session_factory):
    gestore = GestoreDipendenti(session_factory)

    risultato = gestore.inserisci_dipendente(
        "D1", "Mario", "Rossi", "RSSMRA80A01H501U", datetime(2020, 1, 1), flg_certificazione_gas=True
    )

    assert risultato.ok
    assert risultato.dipendente_id == "D1"
    with session_factory() as session:
        dip = session.get(Dipendente, "D1")
        assert dip.nome == "Mario"
        assert dip.cognome == "Rossi"
        assert dip.codice_fiscale == "RSSMRA80A01H501U"
        assert dip.flg_attivo is True
        assert dip.flg_certificazione_gas is True
        assert dip.data_licenziamento is None


def test_inserisci_dipendente_id_duplicato_rifiutato(session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))

    risultato = gestore.inserisci_dipendente("D1", "Luca", "Bianchi", "CF2", datetime(2021, 1, 1))

    assert not risultato.ok
    assert "gia'" in risultato.motivo
    with session_factory() as session:
        assert session.get(Dipendente, "D1").nome == "Mario"


def test_inserisci_dipendente_codice_fiscale_duplicato_rifiutato(session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF-STESSO", datetime(2020, 1, 1))

    risultato = gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF-STESSO", datetime(2021, 1, 1))

    assert not risultato.ok
    assert "Codice fiscale" in risultato.motivo
    with session_factory() as session:
        assert session.get(Dipendente, "D2") is None


def test_modifica_dipendente_aggiorna_solo_i_campi_passati(session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))

    risultato = gestore.modifica_dipendente("D1", cognome="Verdi", flg_certificazione_gas=True)

    assert risultato.ok
    with session_factory() as session:
        dip = session.get(Dipendente, "D1")
        assert dip.nome == "Mario"
        assert dip.cognome == "Verdi"
        assert dip.flg_certificazione_gas is True
        assert dip.codice_fiscale == "CF1"


def test_modifica_dipendente_non_espone_un_parametro_id(session_factory):
    # RF2: l'identificativo di sistema non deve mai essere alterabile - non compare tra i
    # parametri di modifica_dipendente (a differenza di id_, usato solo per la ricerca).
    import inspect

    parametri = inspect.signature(GestoreDipendenti.modifica_dipendente).parameters
    assert "id" not in parametri


def test_modifica_dipendente_inesistente_rifiutata(session_factory):
    gestore = GestoreDipendenti(session_factory)

    risultato = gestore.modifica_dipendente("INESISTENTE", nome="X")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_licenzia_dipendente(session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D1", datetime(2026, 7, 20))

    assert risultato.ok
    with session_factory() as session:
        dip = session.get(Dipendente, "D1")
        assert dip.flg_attivo is False
        assert dip.data_licenziamento == datetime(2026, 7, 20)
        # RF3: il record resta a database (storico), non viene cancellato fisicamente.
        assert dip is not None


def test_licenzia_dipendente_gia_licenziato_rifiutato(session_factory):
    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.licenzia_dipendente("D1")

    risultato = gestore.licenzia_dipendente("D1")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_licenzia_dipendente_inesistente_rifiutato(session_factory):
    gestore = GestoreDipendenti(session_factory)

    risultato = gestore.licenzia_dipendente("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo
