from datetime import datetime

import pytest

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra, Viaggio
from gestionale_logistica.risorse.gestore_camion import (
    FILTRO_TUTTI,
    STATO_ATTIVO,
    STATO_DISMESSO,
    STATO_IN_VIAGGIO,
    GestoreCamion,
)


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


@pytest.mark.parametrize(
    "targa_non_valida",
    ["AB123C", "A1234BC", "AB1234C", "AB123CDE", "1B123CD", "", "AB-123-CD"],
)
def test_inserisci_camion_targa_mal_formata_rifiutata(session_factory, targa_non_valida):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.inserisci_camion(
        "C1", targa_non_valida, "Furgone", datetime(2020, 1, 1), 100.0, 5.0
    )

    assert not risultato.ok
    assert "non valida" in risultato.motivo
    with session_factory() as session:
        assert session.get(Camion, "C1") is None


def test_inserisci_camion_targa_minuscola_ammessa(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.inserisci_camion("C1", "ab123cd", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    assert risultato.ok


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


def test_modifica_camion_targa_mal_formata_rifiutata(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.modifica_camion("C1", targa="INVALIDA")

    assert not risultato.ok
    assert "non valida" in risultato.motivo
    with session_factory() as session:
        assert session.get(Camion, "C1").targa == "AB123CD"


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


def test_riattiva_camion(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.disattiva_camion("C1", datetime(2026, 7, 20))

    risultato = gestore.riattiva_camion("C1")

    assert risultato.ok
    with session_factory() as session:
        mezzo = session.get(Camion, "C1")
        assert mezzo.flg_attivo is True
        assert mezzo.data_dismissione is None


def test_riattiva_camion_gia_attivo_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.riattiva_camion("C1")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


def test_riattiva_camion_inesistente_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.riattiva_camion("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def crea_dipendente(id_):
    return Dipendente(
        id=id_, nome="Nome", cognome="Cognome", codice_fiscale=f"CF-{id_}",
        data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
        flg_attivo=True, flg_certificazione_gas=False,
    )


def test_disattiva_camion_disattiva_a_cascata_le_composizioni_attive_che_lo_contengono(session_factory):
    # Stesso scenario "zombie" della cascata su licenzia_dipendente, versione camion: senza,
    # avvia_composizione_viaggio (RF10) accetterebbe la composizione (flg_attiva ancora True)
    # nonostante il camion non sia piu' idoneo.
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(crea_dipendente("D1"))
        session.add(crea_dipendente("D2"))
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.disattiva_camion("CAM1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is False


def test_disattiva_camion_non_disattiva_composizioni_di_altri_camion(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(crea_dipendente("D1"))
        session.add(crea_dipendente("D2"))
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM2",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("CAM2", "XY999ZZ", "Camion", datetime(2020, 1, 1), 200.0, 10.0)

    gestore.disattiva_camion("CAM1")

    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is True


def test_disattiva_camion_rifiutato_se_gia_coinvolto_in_viaggio_in_composizione(session_factory):
    # Stesso scenario "zombie" segnalato in review per licenzia_dipendente, versione camion: un
    # Viaggio IN_COMPOSIZIONE aperto prima della dismissione non e' toccato dalla sola cascata su
    # ComposizioneSquadra, quindi la dismissione va rifiutata a monte.
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(crea_dipendente("D1"))
        session.add(crea_dipendente("D2"))
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime(2026, 7, 20, 8, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_COMPOSIZIONE, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.disattiva_camion("CAM1")

    assert not risultato.ok
    assert "V1" in risultato.motivo
    with session_factory() as session:
        assert session.get(Camion, "CAM1").flg_attivo is True
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is True


def test_disattiva_camion_rifiutato_se_coinvolto_in_viaggio_in_corso(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(crea_dipendente("D1"))
        session.add(crea_dipendente("D2"))
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime(2026, 7, 20, 8, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    risultato = gestore.disattiva_camion("CAM1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Camion, "CAM1").flg_attivo is True


def test_visualizza_camion_su_db_vuoto(session_factory):
    gestore = GestoreCamion(session_factory)

    pagina = gestore.visualizza_camion()

    assert pagina.camion == []
    assert pagina.totale == 0


def test_visualizza_camion_campi(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion(
        "C1", "AB123CD", "Furgone", datetime(2020, 1, 1), peso_massimo=1200.0,
        volume_massimo=8.0, flg_sponda_idraulica=True,
    )

    pagina = gestore.visualizza_camion()

    assert pagina.totale == 1
    riga = pagina.camion[0]
    assert riga.id == "C1"
    assert riga.targa == "AB123CD"
    assert riga.tipo_mezzo == "Furgone"
    assert riga.peso_massimo == 1200.0
    assert riga.volume_massimo == 8.0
    assert riga.flg_sponda_idraulica is True
    assert riga.data_acquisizione == datetime(2020, 1, 1)
    assert riga.stato == STATO_ATTIVO


def test_visualizza_camion_stato_in_viaggio_solo_per_composizione_in_corso(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(crea_dipendente("D1"))
        session.add(crea_dipendente("D2"))
        session.add(
            ComposizioneSquadra(
                id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
                dipendente_1_id="D1", dipendente_2_id="D2",
                data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
            )
        )
        session.add(
            Viaggio(
                id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
                data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime(2026, 7, 20, 8, 0),
                km_percorsi=None,
                stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="C1",
            )
        )
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)

    pagina = gestore.visualizza_camion()

    assert pagina.camion[0].stato == STATO_IN_VIAGGIO


def test_visualizza_camion_stato_dismesso(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.disattiva_camion("C1")

    pagina = gestore.visualizza_camion()

    assert pagina.camion[0].stato == STATO_DISMESSO


def test_visualizza_camion_ricerca_su_targa_e_tipo_mezzo(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 200.0, 10.0)

    assert [r.id for r in gestore.visualizza_camion(ricerca="ab123").camion] == ["C1"]
    assert [r.id for r in gestore.visualizza_camion(ricerca="motrice").camion] == ["C2"]
    assert gestore.visualizza_camion(ricerca="nessuno").camion == []


def test_visualizza_camion_filtro_tipo(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 200.0, 10.0)

    pagina = gestore.visualizza_camion(filtro_tipo="Furgone")

    assert [r.id for r in pagina.camion] == ["C1"]


def test_visualizza_camion_filtro_stato(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 200.0, 10.0)
    gestore.disattiva_camion("C2")

    solo_attivi = gestore.visualizza_camion(filtro_stato=STATO_ATTIVO).camion
    solo_dismessi = gestore.visualizza_camion(filtro_stato=STATO_DISMESSO).camion
    tutti = gestore.visualizza_camion(filtro_stato=FILTRO_TUTTI).camion

    assert [r.id for r in solo_attivi] == ["C1"]
    assert [r.id for r in solo_dismessi] == ["C2"]
    assert len(tutti) == 2


def test_visualizza_camion_ordinamento_per_data_acquisizione(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2022, 1, 1), 100.0, 5.0)
    gestore.inserisci_camion("C2", "XY999ZZ", "Motrice", datetime(2020, 1, 1), 200.0, 10.0)

    crescente = gestore.visualizza_camion().camion
    decrescente = gestore.visualizza_camion(decrescente=True).camion

    assert [r.id for r in crescente] == ["C2", "C1"]
    assert [r.id for r in decrescente] == ["C1", "C2"]


def test_visualizza_camion_paginazione(session_factory):
    gestore = GestoreCamion(session_factory)
    for i in range(5):
        gestore.inserisci_camion(
            f"C{i}", f"TG{i:03d}AA", "Furgone", datetime(2020, 1, 1 + i), 100.0, 5.0
        )

    pagina_1 = gestore.visualizza_camion(pagina=1, dimensione_pagina=2)
    pagina_2 = gestore.visualizza_camion(pagina=2, dimensione_pagina=2)

    assert pagina_1.totale == 5
    assert [r.id for r in pagina_1.camion] == ["C0", "C1"]
    assert [r.id for r in pagina_2.camion] == ["C2", "C3"]


def test_elimina_camion_definitivamente(session_factory):
    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("C1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)

    risultato = gestore.elimina_camion_definitivamente("C1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Camion, "C1") is None


def test_elimina_camion_definitivamente_inesistente_rifiutato(session_factory):
    gestore = GestoreCamion(session_factory)

    risultato = gestore.elimina_camion_definitivamente("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_elimina_camion_definitivamente_rifiutato_se_membro_di_composizione(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
        session.add(Dipendente(
            id="D1", nome="Mario", cognome="Rossi", codice_fiscale="AAAAAA80A01A001A",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.add(Dipendente(
            id="D2", nome="Luca", cognome="Bianchi", codice_fiscale="BBBBBB80A01A002A",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=True, flg_certificazione_gas=False,
        ))
        session.add(ComposizioneSquadra(
            id_composizione="C1", squadra_id="SQ1", camion_id="CAM1",
            dipendente_1_id="D1", dipendente_2_id="D2",
            data_inizio_validita=datetime(2020, 1, 1), data_fine_validita=None, flg_attiva=True,
        ))
        session.commit()

    gestore = GestoreCamion(session_factory)
    gestore.inserisci_camion("CAM1", "AB123CD", "Furgone", datetime(2020, 1, 1), 1200.0, 8.0)

    risultato = gestore.elimina_camion_definitivamente("CAM1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Camion, "CAM1") is not None
