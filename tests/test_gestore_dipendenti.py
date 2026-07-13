from datetime import datetime

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra, Viaggio
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


def test_licenzia_dipendente_disattiva_a_cascata_le_composizioni_attive_che_lo_contengono(session_factory):
    # Senza la cascata, avvia_composizione_viaggio (RF10) accetterebbe ancora la composizione
    # (controlla solo composizione.flg_attiva) nonostante il dipendente non sia piu' idoneo,
    # producendo un Viaggio IN_COMPOSIZIONE bloccato indefinitamente (nessun ordine puo' mai
    # essere aggiunto, la chiusura richiede almeno un ordine).
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(
            Camion(
                id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
                flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
                flg_attivo=True,
            )
        )
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is False


def test_licenzia_dipendente_non_disattiva_composizioni_di_altri_dipendenti(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(
            Camion(
                id="CAM1", targa="AB123CD", tipo_mezzo="Furgone", peso_massimo=100.0, volume_massimo=5.0,
                flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1), data_dismissione=None,
                flg_attivo=True,
            )
        )
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D2", dipendente_2_id="D3",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D3", "Anna", "Neri", "CF3", datetime(2020, 1, 1))

    gestore.licenzia_dipendente("D1")

    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is True


def crea_squadra_con_composizione(session, comp_id="C1", camion_id="CAM1", d1="D1", d2="D2"):
    session.add(Squadra(id=f"SQ-{comp_id}", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(
        Camion(
            id=camion_id, targa=f"TARGA-{camion_id}", tipo_mezzo="Furgone", peso_massimo=100.0,
            volume_massimo=5.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
            data_dismissione=None, flg_attivo=True,
        )
    )
    session.add(
        ComposizioneSquadra(
            id_composizione=comp_id, squadra_id=f"SQ-{comp_id}", camion_id=camion_id,
            dipendente_1_id=d1, dipendente_2_id=d2,
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        )
    )


def test_licenzia_dipendente_rifiutato_se_gia_coinvolto_in_viaggio_in_composizione(session_factory):
    # Riproduce lo scenario segnalato in review: un Viaggio IN_COMPOSIZIONE aperto *prima* del
    # licenziamento non viene toccato dalla sola cascata su ComposizioneSquadra (che agisce solo
    # sulle richieste future di avvia_composizione_viaggio) - senza questo controllo a monte,
    # nessun ordine potrebbe mai piu' essere aggiunto al viaggio (verifica_idoneita_risorsa
    # rifiuta sempre) e chiudi_composizione_viaggio non potrebbe mai chiuderlo (richiede almeno
    # un ordine): uno "zombie" bloccato indefinitamente.
    with session_factory() as session:
        crea_squadra_con_composizione(session, "C1")
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_COMPOSIZIONE, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D1")

    assert not risultato.ok
    assert "V1" in risultato.motivo
    with session_factory() as session:
        assert session.get(Dipendente, "D1").flg_attivo is True
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is True


def test_licenzia_dipendente_rifiutato_se_coinvolto_in_viaggio_in_corso(session_factory):
    with session_factory() as session:
        crea_squadra_con_composizione(session, "C1")
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Dipendente, "D1").flg_attivo is True


def test_licenzia_dipendente_ammesso_se_viaggio_collegato_e_gia_pianificato(session_factory):
    # Un Viaggio Pianificato non e' piu' modificabile (aggiungi_ordine_a_viaggio richiede
    # IN_COMPOSIZIONE), quindi non puo' diventare zombie: il licenziamento deve restare ammesso.
    with session_factory() as session:
        crea_squadra_con_composizione(session, "C1")
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), km_percorsi=None,
                stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is False


def test_licenzia_dipendente_2_disattiva_a_cascata_la_composizione(session_factory):
    # Copertura del secondo slot (dipendente_2_id), stesso ramo dell'or_ nella query di
    # licenzia_dipendente ma finora mai esercitato da un test dedicato.
    with session_factory() as session:
        crea_squadra_con_composizione(session, "C1")
        session.commit()

    gestore = GestoreDipendenti(session_factory)
    gestore.inserisci_dipendente("D1", "Mario", "Rossi", "CF1", datetime(2020, 1, 1))
    gestore.inserisci_dipendente("D2", "Luca", "Bianchi", "CF2", datetime(2020, 1, 1))

    risultato = gestore.licenzia_dipendente("D2")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is False
