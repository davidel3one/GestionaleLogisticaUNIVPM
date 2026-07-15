from datetime import datetime

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    ComposizioneSquadra,
    Dipendente,
    Ordine,
    Squadra,
    Viaggio,
)
from gestionale_logistica.risorse.gestore_squadre import (
    STATO_ATTIVA,
    STATO_IN_VIAGGIO,
    STATO_NON_ATTIVA,
    GestoreSquadre,
)


def inserisci_camion(session, id_="CAM1", flg_attivo=True, targa=None):
    session.add(
        Camion(
            id=id_, targa=targa or f"TARGA-{id_}", tipo_mezzo="Furgone", peso_massimo=100.0,
            volume_massimo=5.0, flg_sponda_idraulica=False, data_acquisizione=datetime(2020, 1, 1),
            data_dismissione=None, flg_attivo=flg_attivo,
        )
    )


def inserisci_dipendente(session, id_, flg_attivo=True, nome="Mario", cognome="Rossi"):
    session.add(
        Dipendente(
            id=id_, nome=nome, cognome=cognome, codice_fiscale=f"CF-{id_}",
            data_assunzione=datetime(2020, 1, 1), data_licenziamento=None,
            flg_attivo=flg_attivo, flg_certificazione_gas=False,
        )
    )


def inserisci_composizione(session, id_comp, squadra_id, camion_id="CAM1", d1="D1", d2="D2",
                           data_inizio=datetime(2026, 1, 1), flg_attiva=True):
    session.add(
        ComposizioneSquadra(
            id_composizione=id_comp, squadra_id=squadra_id, camion_id=camion_id,
            dipendente_1_id=d1, dipendente_2_id=d2, data_inizio_validita=data_inizio,
            data_fine_validita=None, flg_attiva=flg_attiva,
        )
    )


def inserisci_viaggio(session, id_, composizione_id, stato, data_partenza=datetime(2026, 2, 1)):
    session.add(
        Viaggio(
            id=id_, data_partenza_prevista=data_partenza, data_arrivo_prevista=data_partenza,
            km_percorsi=None, stato_viaggio=stato, composizione_id=composizione_id,
        )
    )


def inserisci_ordine(session, id_, viaggio_id):
    session.add(
        Ordine(
            id=id_, indirizzo="Via Roma 1", comune="Ancona", provincia="AN", lat=None, lon=None,
            cliente="ACME", peso=10.0, volume_cargo=1.0,
            categoria_consegna=CategoriaConsegna.BORDO_STRADA, stato_ordine=StatoOrdine.PIANIFICATO,
            data_consegna=None, viaggio_id=viaggio_id, negozio_partner=None,
        )
    )


def _squadra_con_composizione(session, squadra_id, flg_attiva_squadra=True, targa=None,
                              nome1="Mario", cognome1="Bianchi", nome2="Elena", cognome2="Conti",
                              data_creazione=datetime(2026, 1, 1)):
    """Crea una squadra con camion + 2 dipendenti dedicati e una composizione attiva. Camion e
    dipendenti hanno id derivati dallo squadra_id per non collidere tra piu' squadre nello stesso test."""
    cam_id = f"CAM-{squadra_id}"
    d1_id = f"{squadra_id}-D1"
    d2_id = f"{squadra_id}-D2"
    inserisci_camion(session, cam_id, targa=targa or f"TARGA-{squadra_id}")
    inserisci_dipendente(session, d1_id, nome=nome1, cognome=cognome1)
    inserisci_dipendente(session, d2_id, nome=nome2, cognome=cognome2)
    session.add(Squadra(id=squadra_id, flg_attiva=flg_attiva_squadra, data_creazione=data_creazione))
    inserisci_composizione(session, f"C-{squadra_id}", squadra_id, camion_id=cam_id, d1=d1_id, d2=d2_id)
    return f"C-{squadra_id}"


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


# ---------- visualizza_squadre: stati derivati ----------


def test_visualizza_squadre_stato_attiva(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1")
        session.commit()

    pagina = GestoreSquadre(session_factory).visualizza_squadre()

    assert pagina.totale == 1
    vista = pagina.squadre[0]
    assert vista.stato == STATO_ATTIVA
    assert vista.membri == "Mario Bianchi, Elena Conti"
    assert vista.camion == "TARGA-SQ1"


def test_visualizza_squadre_stato_in_viaggio_solo_in_corso(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp, StatoViaggio.IN_CORSO)
        session.commit()

    pagina = GestoreSquadre(session_factory).visualizza_squadre()

    assert pagina.squadre[0].stato == STATO_IN_VIAGGIO


def test_visualizza_squadre_in_composizione_non_da_in_viaggio(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp, StatoViaggio.IN_COMPOSIZIONE)
        inserisci_viaggio(session, "V2", comp, StatoViaggio.PIANIFICATO)
        session.commit()

    pagina = GestoreSquadre(session_factory).visualizza_squadre()

    assert pagina.squadre[0].stato == STATO_ATTIVA


def test_visualizza_squadre_stato_non_attiva(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1", flg_attiva_squadra=False)
        session.commit()

    gestore = GestoreSquadre(session_factory)

    # Di default (nessun filtro / FILTRO_TUTTE) le squadre Non attiva restano nascoste: si vedono
    # solo scegliendo esplicitamente il filtro Stato "Non attiva".
    assert gestore.visualizza_squadre().totale == 0
    pagina_non_attiva = gestore.visualizza_squadre(filtro_stato=STATO_NON_ATTIVA)
    assert pagina_non_attiva.squadre[0].stato == STATO_NON_ATTIVA


def test_visualizza_squadre_senza_composizione_placeholder(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2026, 1, 1)))
        session.commit()

    vista = GestoreSquadre(session_factory).visualizza_squadre().squadre[0]

    assert vista.membri == "—"
    assert vista.camion == "—"


# ---------- visualizza_squadre: ricerca / filtro / ordinamento / paginazione ----------


def test_visualizza_squadre_ricerca_per_dipendente(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1", nome2="Elena", cognome2="Verdi")
        _squadra_con_composizione(session, "SQ2", nome1="Luca", cognome1="Neri", nome2="Ada", cognome2="Blu")
        session.commit()

    pagina = GestoreSquadre(session_factory).visualizza_squadre(ricerca="verdi")

    assert pagina.totale == 1
    assert pagina.squadre[0].id == "SQ1"


def test_visualizza_squadre_ricerca_per_targa(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1", targa="AB123CD")
        _squadra_con_composizione(session, "SQ2", targa="ZZ999ZZ")
        session.commit()

    pagina = GestoreSquadre(session_factory).visualizza_squadre(ricerca="ab123")

    assert pagina.totale == 1
    assert pagina.squadre[0].id == "SQ1"


def test_visualizza_squadre_filtro_stato(session_factory):
    with session_factory() as session:
        comp1 = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp1, StatoViaggio.IN_CORSO)
        _squadra_con_composizione(session, "SQ2")
        _squadra_con_composizione(session, "SQ3", flg_attiva_squadra=False)
        session.commit()

    gestore = GestoreSquadre(session_factory)

    assert [s.id for s in gestore.visualizza_squadre(filtro_stato=STATO_IN_VIAGGIO).squadre] == ["SQ1"]
    assert [s.id for s in gestore.visualizza_squadre(filtro_stato=STATO_ATTIVA).squadre] == ["SQ2"]
    assert [s.id for s in gestore.visualizza_squadre(filtro_stato=STATO_NON_ATTIVA).squadre] == ["SQ3"]
    # Default (FILTRO_TUTTE): SQ3 (Non attiva) resta escluso, solo SQ1+SQ2.
    assert gestore.visualizza_squadre().totale == 2


def test_visualizza_squadre_ordinamento_per_data_creazione(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ_VECCHIA", data_creazione=datetime(2025, 1, 1))
        _squadra_con_composizione(session, "SQ_NUOVA", data_creazione=datetime(2026, 6, 1))
        session.commit()

    gestore = GestoreSquadre(session_factory)

    crescente = [s.id for s in gestore.visualizza_squadre().squadre]
    decrescente = [s.id for s in gestore.visualizza_squadre(decrescente=True).squadre]

    assert crescente == ["SQ_VECCHIA", "SQ_NUOVA"]
    assert decrescente == ["SQ_NUOVA", "SQ_VECCHIA"]


def test_visualizza_squadre_paginazione(session_factory):
    with session_factory() as session:
        for i in range(5):
            _squadra_con_composizione(session, f"SQ{i}", data_creazione=datetime(2026, 1, i + 1))
        session.commit()

    gestore = GestoreSquadre(session_factory)

    pagina1 = gestore.visualizza_squadre(pagina=1, dimensione_pagina=2)
    pagina3 = gestore.visualizza_squadre(pagina=3, dimensione_pagina=2)

    assert pagina1.totale == 5
    assert [s.id for s in pagina1.squadre] == ["SQ0", "SQ1"]
    assert [s.id for s in pagina3.squadre] == ["SQ4"]


# ---------- dettaglio_squadra ----------


def test_dettaglio_squadra_inesistente_ritorna_none(session_factory):
    assert GestoreSquadre(session_factory).dettaglio_squadra("SQ-X") is None


def test_dettaglio_squadra_viaggi_ordinati_desc_con_n_ordini(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V_VECCHIO", comp, StatoViaggio.COMPLETATO, datetime(2026, 1, 1))
        inserisci_viaggio(session, "V_NUOVO", comp, StatoViaggio.IN_CORSO, datetime(2026, 5, 1))
        inserisci_ordine(session, "O1", "V_NUOVO")
        inserisci_ordine(session, "O2", "V_NUOVO")
        inserisci_ordine(session, "O3", "V_VECCHIO")
        session.commit()

    dettaglio = GestoreSquadre(session_factory).dettaglio_squadra("SQ1")

    assert dettaglio.stato == STATO_IN_VIAGGIO
    assert dettaglio.membri == "Mario Bianchi, Elena Conti"
    assert [v.id_viaggio for v in dettaglio.viaggi] == ["V_NUOVO", "V_VECCHIO"]
    assert dettaglio.viaggi[0].n_ordini == 2
    assert dettaglio.viaggi[0].stato_viaggio == StatoViaggio.IN_CORSO
    assert dettaglio.viaggi[1].n_ordini == 1


def test_dettaglio_squadra_viaggi_su_tutte_le_composizioni(session_factory):
    with session_factory() as session:
        comp1 = _squadra_con_composizione(session, "SQ1")
        # seconda composizione (storica, non attiva) della stessa squadra
        inserisci_composizione(session, "C-STORICA", "SQ1", camion_id="CAM-SQ1",
                               d1="SQ1-D1", d2="SQ1-D2", data_inizio=datetime(2025, 1, 1),
                               flg_attiva=False)
        inserisci_viaggio(session, "V_ATTUALE", comp1, StatoViaggio.COMPLETATO, datetime(2026, 3, 1))
        inserisci_viaggio(session, "V_STORICO", "C-STORICA", StatoViaggio.COMPLETATO, datetime(2025, 3, 1))
        session.commit()

    dettaglio = GestoreSquadre(session_factory).dettaglio_squadra("SQ1")

    assert {v.id_viaggio for v in dettaglio.viaggi} == {"V_ATTUALE", "V_STORICO"}


def test_dettaglio_squadra_senza_composizione_e_senza_viaggi(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=True, data_creazione=datetime(2026, 1, 1)))
        session.commit()

    dettaglio = GestoreSquadre(session_factory).dettaglio_squadra("SQ1")

    assert dettaglio.membri == "—"
    assert dettaglio.camion == "—"
    assert dettaglio.stato == STATO_ATTIVA
    assert dettaglio.viaggi == []


# ---------- elimina_squadra ----------


def test_elimina_squadra_soft_delete_con_cascata(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1")
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra("SQ1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Squadra, "SQ1").flg_attiva is False
        assert session.get(ComposizioneSquadra, "C-SQ1").flg_attiva is False


def test_elimina_squadra_rifiutata_con_viaggio_in_corso(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp, StatoViaggio.IN_CORSO)
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra("SQ1")

    assert not risultato.ok
    assert "in corso" in risultato.motivo
    with session_factory() as session:
        assert session.get(Squadra, "SQ1").flg_attiva is True


def test_elimina_squadra_ammessa_con_solo_in_composizione(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp, StatoViaggio.IN_COMPOSIZIONE)
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra("SQ1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Squadra, "SQ1").flg_attiva is False


def test_elimina_squadra_inesistente_rifiutata(session_factory):
    risultato = GestoreSquadre(session_factory).elimina_squadra("SQ-X")

    assert not risultato.ok
    assert "non trovata" in risultato.motivo


def test_elimina_squadra_gia_non_attiva_rifiutata(session_factory):
    with session_factory() as session:
        session.add(Squadra(id="SQ1", flg_attiva=False, data_creazione=datetime(2026, 1, 1)))
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra("SQ1")

    assert not risultato.ok
    assert "gia'" in risultato.motivo


# ---------- elimina_squadra_definitivamente ----------


def test_elimina_squadra_definitivamente_rimuove_squadra_e_composizioni(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1", flg_attiva_squadra=False)
        inserisci_composizione(session, "C-SQ1-OLD", "SQ1", flg_attiva=False)
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra_definitivamente("SQ1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Squadra, "SQ1") is None
        assert session.get(ComposizioneSquadra, "C-SQ1") is None
        assert session.get(ComposizioneSquadra, "C-SQ1-OLD") is None


def test_elimina_squadra_definitivamente_rifiutata_se_ancora_attiva(session_factory):
    with session_factory() as session:
        _squadra_con_composizione(session, "SQ1")
        session.commit()

    risultato = GestoreSquadre(session_factory).elimina_squadra_definitivamente("SQ1")

    assert not risultato.ok
    assert "ancora attiva" in risultato.motivo
    with session_factory() as session:
        assert session.get(Squadra, "SQ1") is not None


def test_elimina_squadra_definitivamente_rifiutata_con_storico_viaggi(session_factory):
    with session_factory() as session:
        comp = _squadra_con_composizione(session, "SQ1")
        inserisci_viaggio(session, "V1", comp, StatoViaggio.COMPLETATO)
        session.commit()

    GestoreSquadre(session_factory).elimina_squadra("SQ1")
    risultato = GestoreSquadre(session_factory).elimina_squadra_definitivamente("SQ1")

    assert not risultato.ok
    assert "storico" in risultato.motivo
    with session_factory() as session:
        assert session.get(Squadra, "SQ1") is not None


def test_elimina_squadra_definitivamente_inesistente_rifiutata(session_factory):
    risultato = GestoreSquadre(session_factory).elimina_squadra_definitivamente("SQ-X")

    assert not risultato.ok
    assert "non trovata" in risultato.motivo


# ---------- prossimo_id_squadra ----------


def test_prossimo_id_squadra_senza_squadre(session_factory):
    assert GestoreSquadre(session_factory).prossimo_id_squadra() == "1"


def test_prossimo_id_squadra_dopo_creazioni(session_factory):
    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("1")
    gestore.crea_squadra("2")

    assert gestore.prossimo_id_squadra() == "3"


def test_prossimo_id_squadra_non_collide_con_squadra_non_attiva(session_factory):
    gestore = GestoreSquadre(session_factory)
    gestore.crea_squadra("1")
    gestore.crea_squadra("2")
    gestore.elimina_squadra("1")

    # SQ "1" e' Non attiva (non piu' visibile in lista di default) ma resta a DB: il prossimo id
    # deve comunque evitarla, non basarsi solo sul conteggio delle squadre visibili.
    assert gestore.prossimo_id_squadra() == "3"


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
