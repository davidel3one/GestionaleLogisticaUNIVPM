from datetime import datetime, timedelta

from gestionale_logistica.database.enums import CategoriaConsegna, StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    ComposizioneSquadra,
    Dipendente,
    EsitoConsegna,
    Ordine,
    RegistroEsiti,
    Squadra,
    Viaggio,
)
from gestionale_logistica.logistica.gestore_logistica import (
    FILTRO_TUTTI,
    GestoreLogistica,
    valida_ordine_per_viaggio,
    verifica_idoneita_risorsa,
)
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import MotoreOttimizzazione
from gestionale_logistica.risorse.gestore_dipendenti import GestoreDipendenti


def crea_dipendente(id_, certificazione_gas=False, attivo=True):
    return Dipendente(
        id=id_,
        nome="Nome",
        cognome="Cognome",
        codice_fiscale=f"CF-{id_}",
        data_assunzione=datetime(2020, 1, 1),
        data_licenziamento=None,
        flg_attivo=attivo,
        flg_certificazione_gas=certificazione_gas,
    )


def crea_camion(id_, peso_massimo=100.0, volume_massimo=5.0, sponda_idraulica=False, attivo=True):
    return Camion(
        id=id_,
        targa=f"TARGA-{id_}",
        tipo_mezzo="Furgone",
        peso_massimo=peso_massimo,
        volume_massimo=volume_massimo,
        flg_sponda_idraulica=sponda_idraulica,
        data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None,
        flg_attivo=attivo,
    )


def crea_composizione(
    id_,
    camion_id,
    dipendente_1_id,
    dipendente_2_id,
    data_inizio=datetime(2020, 1, 1),
    data_fine=None,
    attiva=True,
):
    return ComposizioneSquadra(
        id_composizione=id_,
        squadra_id=id_,
        camion_id=camion_id,
        dipendente_1_id=dipendente_1_id,
        dipendente_2_id=dipendente_2_id,
        data_inizio_validita=data_inizio,
        data_fine_validita=data_fine,
        flg_attiva=attiva,
    )


def crea_ordine(id_, peso=10.0, volume=0.1, categoria=CategoriaConsegna.BORDO_STRADA):
    return Ordine(
        id=id_,
        indirizzo="Via Test 1",
        comune="Ancona",
        provincia="AN",
        lat=None,
        lon=None,
        cliente="Cliente Test",
        peso=peso,
        volume_cargo=volume,
        categoria_consegna=categoria,
        stato_ordine=StatoOrdine.RICEVUTO,
        data_importazione=datetime.now(),
        data_consegna=None,
        viaggio_id=None,
    )


def crea_flotta_semplice(
    session,
    comp_id="C1",
    peso_massimo=100.0,
    volume_massimo=5.0,
    sponda=False,
    gas=False,
    attiva=True,
    data_inizio=datetime(2020, 1, 1),
    data_fine=None,
):
    session.add(Squadra(id=comp_id, flg_attiva=True, data_creazione=datetime(2020, 1, 1)))
    session.add(crea_dipendente(f"{comp_id}-D1", certificazione_gas=gas))
    session.add(crea_dipendente(f"{comp_id}-D2", certificazione_gas=False))
    session.add(
        crea_camion(f"{comp_id}-CAM", peso_massimo=peso_massimo, volume_massimo=volume_massimo, sponda_idraulica=sponda)
    )
    session.add(
        crea_composizione(
            comp_id,
            f"{comp_id}-CAM",
            f"{comp_id}-D1",
            f"{comp_id}-D2",
            data_inizio=data_inizio,
            data_fine=data_fine,
            attiva=attiva,
        )
    )


# --- Ciclo completo: avvio -> aggiunte -> chiusura ---


def test_ciclo_completo_avvio_aggiunte_e_chiusura(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.add(crea_ordine("ORD-2", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    ora_partenza = datetime(2026, 7, 20, 8, 0)

    avvio = gestore.avvia_composizione_viaggio("C1", ora_partenza)
    assert avvio.ok
    viaggio_id = avvio.viaggio_id

    esito_1 = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-1")
    assert esito_1.ammesso
    esito_2 = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-2")
    assert esito_2.ammesso

    chiusura = gestore.chiudi_composizione_viaggio(viaggio_id)
    assert chiusura.ok
    assert chiusura.viaggio_id == viaggio_id

    with session_factory() as session:
        viaggio = session.get(Viaggio, viaggio_id)
        assert viaggio.stato_viaggio == StatoViaggio.PIANIFICATO
        assert viaggio.data_partenza_prevista == ora_partenza
        assert viaggio.composizione_id == "C1"

        for ordine_id in ["ORD-1", "ORD-2"]:
            ordine = session.get(Ordine, ordine_id)
            assert ordine.viaggio_id == viaggio_id
            assert ordine.stato_ordine == StatoOrdine.PIANIFICATO


def test_rimuovi_ordine_da_viaggio_lo_riporta_ricevuto(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))
    viaggio_id = avvio.viaggio_id

    assert gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-1").ammesso

    esito = gestore.rimuovi_ordine_da_viaggio(viaggio_id, "ORD-1")
    assert esito.ok
    assert esito.ordine_id == "ORD-1"

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.viaggio_id is None
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO

    # Rimosso, torna candidato: puo' essere aggiunto di nuovo (stesso o altro viaggio)
    assert gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-1").ammesso


def test_rimuovi_ordine_da_viaggio_rifiuta_se_non_in_composizione(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))
    viaggio_id = avvio.viaggio_id
    assert gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-1").ammesso
    assert gestore.chiudi_composizione_viaggio(viaggio_id).ok

    esito = gestore.rimuovi_ordine_da_viaggio(viaggio_id, "ORD-1")
    assert not esito.ok

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-1")
        assert ordine.viaggio_id == viaggio_id


def test_rimuovi_ordine_da_viaggio_rifiuta_ordine_non_agganciato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))
    viaggio_id = avvio.viaggio_id

    esito = gestore.rimuovi_ordine_da_viaggio(viaggio_id, "ORD-1")
    assert not esito.ok


# --- Avvio composizione ---


def test_avvio_composizione_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    avvio = gestore.avvia_composizione_viaggio("INESISTENTE", datetime(2026, 7, 20, 8, 0))

    assert not avvio.ok
    assert avvio.viaggio_id is None
    assert "non trovata" in avvio.motivo


def test_avvio_composizione_non_attiva_rifiutato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", attiva=False)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))

    assert not avvio.ok
    assert "non attiva" in avvio.motivo


def test_avvio_composizione_gia_occupata_stesso_giorno_rifiutato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.commit()

    gestore = GestoreLogistica(session_factory)
    ora_partenza = datetime(2026, 7, 20, 8, 0)

    primo_avvio = gestore.avvia_composizione_viaggio("C1", ora_partenza)
    assert primo_avvio.ok

    secondo_avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 14, 0))

    assert not secondo_avvio.ok
    assert "occupata" in secondo_avvio.motivo


# --- Aggiunta ordine: rifiuti con motivo per ciascun vincolo RF11 ---


def test_aggiungi_ordine_rifiutato_per_idoneita_categoria_big(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", sponda=False)
        session.add(crea_ordine("ORD-BIG", categoria=CategoriaConsegna.BIG))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    esito = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-BIG")

    assert not esito.ammesso
    assert "sponda idraulica" in esito.motivo

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-BIG")
        assert ordine.viaggio_id is None
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO


def test_aggiungi_ordine_rifiutato_per_idoneita_gas(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", gas=False)
        session.add(crea_ordine("ORD-GAS", categoria=CategoriaConsegna.CERTIFICAZIONE_GAS))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    esito = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-GAS")

    assert not esito.ammesso
    assert "certificazione gas" in esito.motivo

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-GAS")
        assert ordine.viaggio_id is None
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO


def test_aggiungi_ordine_rifiutato_per_peso(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=15.0, volume_massimo=5.0)
        session.add(crea_ordine("ORD-PESANTE", peso=20.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    esito = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-PESANTE")

    assert not esito.ammesso
    assert "peso" in esito.motivo.lower()

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-PESANTE")
        assert ordine.viaggio_id is None


def test_aggiungi_ordine_rifiutato_per_volume(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=100.0, volume_massimo=1.0)
        session.add(crea_ordine("ORD-VOLUMINOSO", peso=10.0, volume=2.0))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    esito = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-VOLUMINOSO")

    assert not esito.ammesso
    assert "volume" in esito.motivo.lower()

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-VOLUMINOSO")
        assert ordine.viaggio_id is None


def test_aggiungi_ordine_rifiuto_rispetta_capacita_residua_non_solo_totale(session_factory):
    # Il primo ordine da solo entra; il secondo, sommato al primo, supera la capacita' residua
    # anche se singolarmente rientrerebbe nella capacita' totale del camion.
    with session_factory() as session:
        crea_flotta_semplice(session, "C1", peso_massimo=15.0, volume_massimo=5.0)
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.add(crea_ordine("ORD-2", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    primo = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-1")
    assert primo.ammesso

    secondo = gestore.aggiungi_ordine_a_viaggio(viaggio_id, "ORD-2")
    assert not secondo.ammesso
    assert "peso" in secondo.motivo.lower()


# --- Chiusura ---


def test_chiusura_senza_ordini_rifiutata(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.commit()

    gestore = GestoreLogistica(session_factory)
    viaggio_id = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0)).viaggio_id

    chiusura = gestore.chiudi_composizione_viaggio(viaggio_id)

    assert not chiusura.ok
    assert "senza ordini" in chiusura.motivo

    with session_factory() as session:
        viaggio = session.get(Viaggio, viaggio_id)
        assert viaggio.stato_viaggio == StatoViaggio.IN_COMPOSIZIONE


# --- verifica_idoneita_risorsa: esclusione risorse disattivate (RF3/RF6) ---


def test_verifica_idoneita_risorsa_rifiuta_camion_dismesso_indipendentemente_dalla_categoria():
    ordine = crea_ordine("ORD-1", categoria=CategoriaConsegna.BORDO_STRADA)
    camion_dismesso = crea_camion("C1", attivo=False)
    dipendenti = [crea_dipendente("D1"), crea_dipendente("D2")]

    assert verifica_idoneita_risorsa(ordine, camion_dismesso, dipendenti) is False


def test_verifica_idoneita_risorsa_rifiuta_dipendente_licenziato_indipendentemente_dalla_categoria():
    ordine = crea_ordine("ORD-1", categoria=CategoriaConsegna.BORDO_STRADA)
    camion = crea_camion("C1")
    dipendenti = [crea_dipendente("D1"), crea_dipendente("D2", attivo=False)]

    assert verifica_idoneita_risorsa(ordine, camion, dipendenti) is False


def test_valida_ordine_per_viaggio_motivo_camion_dismesso_non_e_fuorviante():
    # Senza un controllo dedicato, un camion dismesso su un ordine Big finirebbe nel ramo
    # "categoria" e restituirebbe "non ha la sponda idraulica" anche se il camion ce l'ha mai
    # avuta - il vero motivo (dismesso) andrebbe perso.
    ordine = crea_ordine("ORD-1", categoria=CategoriaConsegna.BIG)
    camion_dismesso = crea_camion("C1", sponda_idraulica=True, attivo=False)
    dipendenti = [crea_dipendente("D1"), crea_dipendente("D2")]

    esito = valida_ordine_per_viaggio(ordine, camion_dismesso, dipendenti, peso_occupato=0.0, volume_occupato=0.0)

    assert not esito.ammesso
    assert "servizio" in esito.motivo
    assert "sponda idraulica" not in esito.motivo


def test_valida_ordine_per_viaggio_motivo_dipendente_licenziato_non_e_fuorviante():
    ordine = crea_ordine("ORD-1", categoria=CategoriaConsegna.CERTIFICAZIONE_GAS)
    camion = crea_camion("C1")
    dipendenti = [crea_dipendente("D1", certificazione_gas=True, attivo=False), crea_dipendente("D2")]

    esito = valida_ordine_per_viaggio(ordine, camion, dipendenti, peso_occupato=0.0, volume_occupato=0.0)

    assert not esito.ammesso
    assert "servizio" in esito.motivo
    assert "certificazione gas" not in esito.motivo


def test_licenziamento_dipendente_disattiva_composizione_e_evita_viaggio_zombie(session_factory):
    # Riproduce lo scenario segnalato: senza la disattivazione a cascata in licenzia_dipendente,
    # avvia_composizione_viaggio accetterebbe comunque la composizione (composizione.flg_attiva
    # ancora True), producendo un Viaggio IN_COMPOSIZIONE che nessun ordine potrebbe mai
    # raggiungere (verifica_idoneita_risorsa rifiuta sempre il dipendente licenziato) e che
    # chiudi_composizione_viaggio non potrebbe mai chiudere (richiede almeno un ordine) - uno
    # stato "zombie" indefinito, che occuperebbe anche lo slot-giorno per calcola_piano (RF13).
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    GestoreDipendenti(session_factory).licenzia_dipendente("C1-D1")

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))

    assert not avvio.ok
    assert "non attiva" in avvio.motivo

    with session_factory() as session:
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is False


def test_licenziamento_rifiutato_se_viaggio_in_composizione_gia_aperto_sulla_squadra(session_factory):
    # Variante dello scenario zombie non coperta dal fix precedente: qui avvia_composizione_viaggio
    # viene chiamato *prima* del licenziamento, quindi al momento del licenziamento esiste gia' un
    # Viaggio IN_COMPOSIZIONE (senza ordini) agganciato alla composizione. La sola cascata su
    # ComposizioneSquadra non lo tocca (aggiungi_ordine_a_viaggio controlla solo
    # viaggio.stato_viaggio, mai composizione.flg_attiva): il licenziamento va quindi rifiutato a
    # monte, non solo la composizione disattivata a valle.
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        session.commit()

    gestore = GestoreLogistica(session_factory)
    avvio = gestore.avvia_composizione_viaggio("C1", datetime(2026, 7, 20, 8, 0))
    assert avvio.ok

    risultato = GestoreDipendenti(session_factory).licenzia_dipendente("C1-D1")

    assert not risultato.ok
    assert avvio.viaggio_id in risultato.motivo
    with session_factory() as session:
        assert session.get(Dipendente, "C1-D1").flg_attivo is True
        assert session.get(ComposizioneSquadra, "C1").flg_attiva is True
        assert session.get(Viaggio, avvio.viaggio_id).stato_viaggio == StatoViaggio.IN_COMPOSIZIONE


# --- Invarianti verso RF12/RF13 ---


def test_ordine_in_bozza_manuale_escluso_da_suggerisci_ordini_e_calcola_piano(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "C1")
        crea_flotta_semplice(session, "C2")
        session.add(crea_ordine("ORD-MANUALE", peso=10.0, volume=0.5))
        session.add(crea_ordine("ORD-AUTOMATICO", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    ora_partenza = datetime(2026, 7, 20, 8, 0)
    viaggio_manuale_id = gestore.avvia_composizione_viaggio("C1", ora_partenza).viaggio_id
    esito = gestore.aggiungi_ordine_a_viaggio(viaggio_manuale_id, "ORD-MANUALE")
    assert esito.ammesso

    motore = MotoreOttimizzazione(session_factory)

    suggerimento = motore.suggerisci_ordini(viaggio_manuale_id)
    assert "ORD-MANUALE" not in suggerimento.ordini_suggeriti

    piano = motore.calcola_piano(ora_partenza)
    ordini_assegnati_dal_piano = {oid for a in piano.assegnazioni for oid in a.ordini_ids}
    assert "ORD-MANUALE" not in ordini_assegnati_dal_piano
    assert "ORD-MANUALE" not in piano.ordini_non_assegnati


def test_bozza_aperta_blocca_composizione_per_calcola_piano_stesso_giorno(session_factory):
    with session_factory() as session:
        # Un'unica composizione disponibile: se calcola_piano non vede la bozza aperta,
        # assegnerebbe comunque ORD-1 a C1 (doppia prenotazione della stessa composizione).
        crea_flotta_semplice(session, "C1")
        session.add(crea_ordine("ORD-1", peso=10.0, volume=0.5))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    ora_partenza = datetime(2026, 7, 20, 8, 0)
    avvio = gestore.avvia_composizione_viaggio("C1", ora_partenza)
    assert avvio.ok

    motore = MotoreOttimizzazione(session_factory)
    piano = motore.calcola_piano(ora_partenza)

    assert piano.assegnazioni == []
    assert piano.ordini_non_assegnati == ["ORD-1"]


# --- visualizza_ordini ---


def test_visualizza_ordini_su_db_vuoto(session_factory):
    gestore = GestoreLogistica(session_factory)

    pagina = gestore.visualizza_ordini()

    assert pagina.ordini == []
    assert pagina.totale == 0


def test_visualizza_ordini_campi_senza_viaggio(session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1", peso=45.0, volume=0.3))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini()

    assert pagina.totale == 1
    riga = pagina.ordini[0]
    assert riga.id == "ORD-1"
    assert riga.cliente == "Cliente Test"
    assert riga.indirizzo == "Via Test 1, Ancona"
    assert riga.peso == 45.0
    assert riga.volume_cargo == 0.3
    assert riga.stato == "Da pianificare"
    assert riga.data_arrivo_viaggio is None


def test_visualizza_ordini_data_arrivo_da_viaggio_agganciato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        ordine_1.stato_ordine = StatoOrdine.PIANIFICATO
        session.add(ordine_1)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini()

    assert pagina.ordini[0].data_arrivo_viaggio == datetime(2026, 7, 20, 16, 0)
    assert pagina.ordini[0].stato == "Pianificato"


def test_visualizza_ordini_puo_registrare_esito_solo_su_viaggio_in_corso(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="SQ1",
        ))
        session.add(Viaggio(
            id="V2", data_partenza_prevista=datetime(2026, 7, 21, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 21, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_in_corso = crea_ordine("ORD-IN-CORSO")
        ordine_in_corso.viaggio_id = "V1"
        session.add(ordine_in_corso)
        ordine_pianificato = crea_ordine("ORD-PIANIFICATO")
        ordine_pianificato.viaggio_id = "V2"
        session.add(ordine_pianificato)
        session.add(crea_ordine("ORD-SENZA-VIAGGIO"))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini(dimensione_pagina=0)

    per_id = {r.id: r.puo_registrare_esito for r in pagina.ordini}
    assert per_id["ORD-IN-CORSO"] is True
    assert per_id["ORD-PIANIFICATO"] is False
    assert per_id["ORD-SENZA-VIAGGIO"] is False


def test_visualizza_ordini_puo_registrare_esito_falso_se_gia_registrato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.IN_CORSO, composizione_id="SQ1",
        ))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        session.commit()
        registro = RegistroEsiti(data_riferimento=datetime(2026, 7, 20))
        session.add(registro)
        session.flush()
        session.add(EsitoConsegna(
            stato_esito=StatoEsito.COMPLETATO, data_registrazione=datetime.now(),
            ordine_id="ORD-1", viaggio_id="V1", causale_id=None, registro_id=registro.id,
        ))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini()

    assert pagina.ordini[0].puo_registrare_esito is False


def test_visualizza_ordini_tutte_le_etichette_stato(session_factory):
    with session_factory() as session:
        for i, stato in enumerate([
            StatoOrdine.RICEVUTO, StatoOrdine.PIANIFICATO, StatoOrdine.IN_CONSEGNA,
            StatoOrdine.COMPLETATO, StatoOrdine.FALLITO,
        ]):
            o = crea_ordine(f"ORD-{i}")
            o.stato_ordine = stato
            session.add(o)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini(dimensione_pagina=0)

    etichette = {r.stato for r in pagina.ordini}
    assert etichette == {"Da pianificare", "Pianificato", "In consegna", "Consegnato", "Fallito"}


def test_visualizza_ordini_ricerca_su_cliente_indirizzo_id(session_factory):
    with session_factory() as session:
        o1 = crea_ordine("ORD-AAA")
        o1.cliente = "Mario Rossi"
        o1.indirizzo = "Via Roma 12"
        o1.comune = "Ancona"
        session.add(o1)
        o2 = crea_ordine("ORD-BBB")
        o2.cliente = "Bianchi S.r.l."
        o2.indirizzo = "Via Milano 8"
        o2.comune = "Jesi"
        session.add(o2)
        session.commit()

    gestore = GestoreLogistica(session_factory)

    assert [r.id for r in gestore.visualizza_ordini(ricerca="mario").ordini] == ["ORD-AAA"]
    assert [r.id for r in gestore.visualizza_ordini(ricerca="bianchi").ordini] == ["ORD-BBB"]
    assert [r.id for r in gestore.visualizza_ordini(ricerca="jesi").ordini] == ["ORD-BBB"]
    assert [r.id for r in gestore.visualizza_ordini(ricerca="aaa").ordini] == ["ORD-AAA"]
    assert gestore.visualizza_ordini(ricerca="nessuno").ordini == []


def test_visualizza_ordini_filtro_stato(session_factory):
    with session_factory() as session:
        o1 = crea_ordine("ORD-1")
        session.add(o1)
        o2 = crea_ordine("ORD-2")
        o2.stato_ordine = StatoOrdine.FALLITO
        session.add(o2)
        session.commit()

    gestore = GestoreLogistica(session_factory)

    solo_ricevuti = gestore.visualizza_ordini(filtro_stato="Da pianificare").ordini
    solo_falliti = gestore.visualizza_ordini(filtro_stato="Fallito").ordini
    tutti = gestore.visualizza_ordini(filtro_stato=FILTRO_TUTTI).ordini

    assert [r.id for r in solo_ricevuti] == ["ORD-1"]
    assert [r.id for r in solo_falliti] == ["ORD-2"]
    assert len(tutti) == 2


def test_visualizza_ordini_filtro_data(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        session.add(Viaggio(
            id="V2", data_partenza_prevista=datetime(2026, 7, 21, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 21, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        ordine_2 = crea_ordine("ORD-2")
        ordine_2.viaggio_id = "V2"
        session.add(ordine_2)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_ordini(filtro_data=datetime(2026, 7, 20).date())

    assert [r.id for r in pagina.ordini] == ["ORD-1"]


def test_visualizza_ordini_senza_viaggio_sempre_in_coda(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_con_data = crea_ordine("ORD-CON-DATA")
        ordine_con_data.viaggio_id = "V1"
        session.add(ordine_con_data)
        session.add(crea_ordine("ORD-SENZA-DATA"))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    crescente = gestore.visualizza_ordini().ordini
    decrescente = gestore.visualizza_ordini(decrescente=True).ordini

    assert [r.id for r in crescente] == ["ORD-CON-DATA", "ORD-SENZA-DATA"]
    assert [r.id for r in decrescente] == ["ORD-CON-DATA", "ORD-SENZA-DATA"]


def test_visualizza_ordini_paginazione(session_factory):
    with session_factory() as session:
        for i in range(5):
            session.add(crea_ordine(f"ORD-{i}"))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    pagina_1 = gestore.visualizza_ordini(pagina=1, dimensione_pagina=2)
    pagina_2 = gestore.visualizza_ordini(pagina=2, dimensione_pagina=2)

    assert pagina_1.totale == 5
    assert [r.id for r in pagina_1.ordini] == ["ORD-0", "ORD-1"]
    assert [r.id for r in pagina_2.ordini] == ["ORD-2", "ORD-3"]


def crea_viaggio(
    id_,
    composizione_id,
    stato=StatoViaggio.PIANIFICATO,
    partenza=datetime(2026, 7, 20, 8, 0),
    arrivo=datetime(2026, 7, 20, 16, 0),
):
    return Viaggio(
        id=id_,
        data_partenza_prevista=partenza,
        data_arrivo_prevista=arrivo,
        data_creazione=datetime.now(),
        km_percorsi=None,
        stato_viaggio=stato,
        composizione_id=composizione_id,
    )


# --- visualizza_viaggi ---


def test_visualizza_viaggi_su_db_vuoto(session_factory):
    gestore = GestoreLogistica(session_factory)

    pagina = gestore.visualizza_viaggi()

    assert pagina.viaggi == []
    assert pagina.totale == 0


def test_visualizza_viaggi_campi_e_conteggio_ordini(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.add(crea_ordine("ORD-1"))
        session.add(crea_ordine("ORD-2"))
        session.commit()
        ordine_1 = session.get(Ordine, "ORD-1")
        ordine_2 = session.get(Ordine, "ORD-2")
        ordine_1.viaggio_id = "V1"
        ordine_2.viaggio_id = "V1"
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_viaggi()

    assert pagina.totale == 1
    riga = pagina.viaggi[0]
    assert riga.id == "V1"
    assert riga.squadra_id == "SQ1"
    assert riga.n_ordini == 2
    assert riga.data_partenza_prevista == datetime(2026, 7, 20, 8, 0)
    assert riga.data_arrivo_prevista == datetime(2026, 7, 20, 16, 0)
    assert riga.stato == "Pianificato"


def test_visualizza_viaggi_conteggio_zero_ordini(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_viaggi()

    assert pagina.viaggi[0].n_ordini == 0


def test_visualizza_viaggi_tutte_le_etichette_stato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        stati = [
            StatoViaggio.IN_COMPOSIZIONE,
            StatoViaggio.PIANIFICATO,
            StatoViaggio.IN_CORSO,
            StatoViaggio.COMPLETATO,
            StatoViaggio.ANNULLATO,
        ]
        for i, stato in enumerate(stati):
            session.add(crea_viaggio(f"V{i}", "SQ1", stato=stato))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    pagina = gestore.visualizza_viaggi(dimensione_pagina=0)

    etichette = {r.stato for r in pagina.viaggi}
    assert etichette == {"In composizione", "Pianificato", "In corso", "Completato", "Annullato"}


def test_visualizza_viaggi_ricerca_su_id_e_squadra(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        crea_flotta_semplice(session, "SQ2")
        session.add(crea_viaggio("V-AAA", "SQ1"))
        session.add(crea_viaggio("V-BBB", "SQ2"))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    assert [r.id for r in gestore.visualizza_viaggi(ricerca="aaa").viaggi] == ["V-AAA"]
    assert [r.id for r in gestore.visualizza_viaggi(ricerca="sq2").viaggi] == ["V-BBB"]
    assert gestore.visualizza_viaggi(ricerca="nessuno").viaggi == []


def test_visualizza_viaggi_filtro_stato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.add(crea_viaggio("V2", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    solo_pianificati = gestore.visualizza_viaggi(filtro_stato="Pianificato").viaggi
    solo_annullati = gestore.visualizza_viaggi(filtro_stato="Annullato").viaggi
    tutti = gestore.visualizza_viaggi(filtro_stato=FILTRO_TUTTI).viaggi

    assert [r.id for r in solo_pianificati] == ["V1"]
    assert [r.id for r in solo_annullati] == ["V2"]
    assert len(tutti) == 2


def test_visualizza_viaggi_filtro_data(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", partenza=datetime(2026, 7, 20, 8, 0)))
        session.add(crea_viaggio("V2", "SQ1", partenza=datetime(2026, 7, 21, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    pagina = gestore.visualizza_viaggi(filtro_data=datetime(2026, 7, 20).date())

    assert [r.id for r in pagina.viaggi] == ["V1"]


def test_visualizza_viaggi_ordinamento_per_partenza_o_arrivo(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio(
            "V1", "SQ1",
            partenza=datetime(2026, 7, 20, 8, 0), arrivo=datetime(2026, 7, 20, 20, 0),
        ))
        session.add(crea_viaggio(
            "V2", "SQ1",
            partenza=datetime(2026, 7, 19, 8, 0), arrivo=datetime(2026, 7, 19, 10, 0),
        ))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    per_partenza = gestore.visualizza_viaggi(ordina_per="data_partenza_prevista").viaggi
    per_arrivo = gestore.visualizza_viaggi(ordina_per="data_arrivo_prevista").viaggi

    assert [r.id for r in per_partenza] == ["V2", "V1"]
    assert [r.id for r in per_arrivo] == ["V2", "V1"]


def test_visualizza_viaggi_paginazione(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        for i in range(5):
            session.add(crea_viaggio(f"V{i}", "SQ1", partenza=datetime(2026, 7, 10 + i, 8, 0)))
        session.commit()

    gestore = GestoreLogistica(session_factory)

    pagina_1 = gestore.visualizza_viaggi(pagina=1, dimensione_pagina=2)
    pagina_2 = gestore.visualizza_viaggi(pagina=2, dimensione_pagina=2)

    assert pagina_1.totale == 5
    assert [r.id for r in pagina_1.viaggi] == ["V0", "V1"]
    assert [r.id for r in pagina_2.viaggi] == ["V2", "V3"]


# --- annulla_viaggio ---


def test_annulla_viaggio_da_pianificato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.annulla_viaggio("V1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.ANNULLATO


def test_annulla_viaggio_ammesso_da_in_corso(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.IN_CORSO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.annulla_viaggio("V1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.ANNULLATO


def test_annulla_viaggio_rifiutato_se_gia_completato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.COMPLETATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.annulla_viaggio("V1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.COMPLETATO


def test_annulla_viaggio_rifiutato_se_gia_annullato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.annulla_viaggio("V1")

    assert not risultato.ok


def test_annulla_viaggio_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.annulla_viaggio("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_annulla_viaggio_rimette_gli_ordini_a_ricevuto(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.IN_CORSO))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.stato_ordine = StatoOrdine.IN_CONSEGNA
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.annulla_viaggio("V1")

    assert risultato.ok
    with session_factory() as session:
        ordine_1 = session.get(Ordine, "ORD-1")
        assert ordine_1.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine_1.viaggio_id is None


# --- modifica_date_viaggio ---


def test_modifica_date_viaggio(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    nuova_partenza = datetime(2026, 7, 25, 9, 0)
    nuovo_arrivo = datetime(2026, 7, 25, 17, 0)

    risultato = gestore.modifica_date_viaggio(
        "V1", data_partenza_prevista=nuova_partenza, data_arrivo_prevista=nuovo_arrivo
    )

    assert risultato.ok
    with session_factory() as session:
        viaggio_obj = session.get(Viaggio, "V1")
        assert viaggio_obj.data_partenza_prevista == nuova_partenza
        assert viaggio_obj.data_arrivo_prevista == nuovo_arrivo


def test_modifica_date_viaggio_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.modifica_date_viaggio("INESISTENTE", data_partenza_prevista=datetime(2026, 1, 1))

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_modifica_date_viaggio_rifiutata_se_completato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.COMPLETATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.modifica_date_viaggio("V1", data_partenza_prevista=datetime(2026, 1, 1))

    assert not risultato.ok


# --- ripristina_viaggio ---


def test_ripristina_viaggio_torna_in_composizione(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.ANNULLATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.ripristina_viaggio("V1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.IN_COMPOSIZIONE


def test_ripristina_viaggio_rifiutato_se_non_annullato(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1", stato=StatoViaggio.PIANIFICATO))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.ripristina_viaggio("V1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1").stato_viaggio == StatoViaggio.PIANIFICATO


def test_ripristina_viaggio_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.ripristina_viaggio("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


# --- elimina_viaggio_definitivamente ---


def test_elimina_viaggio_definitivamente(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1"))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.elimina_viaggio_definitivamente("V1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1") is None


def test_elimina_viaggio_definitivamente_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.elimina_viaggio_definitivamente("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


def test_elimina_viaggio_definitivamente_rifiutato_se_ha_ordini(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(crea_viaggio("V1", "SQ1"))
        ordine = crea_ordine("ORD-1")
        ordine.viaggio_id = "V1"
        session.add(ordine)
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.elimina_viaggio_definitivamente("V1")

    assert not risultato.ok
    with session_factory() as session:
        assert session.get(Viaggio, "V1") is not None


# --- elimina_ordine_definitivamente ---


def test_elimina_ordine_definitivamente(session_factory):
    with session_factory() as session:
        session.add(crea_ordine("ORD-1"))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.elimina_ordine_definitivamente("ORD-1")

    assert risultato.ok
    with session_factory() as session:
        assert session.get(Ordine, "ORD-1") is None


def test_elimina_ordine_definitivamente_inesistente_rifiutato(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.elimina_ordine_definitivamente("INESISTENTE")

    assert not risultato.ok
    assert "non trovato" in risultato.motivo


# --- dettaglio_viaggio ---


def test_dettaglio_viaggio_inesistente_none(session_factory):
    gestore = GestoreLogistica(session_factory)
    assert gestore.dettaglio_viaggio("INESISTENTE") is None


def test_dettaglio_viaggio_dipendenti_e_ordini(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None, stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        ordine_1 = crea_ordine("ORD-1")
        ordine_1.viaggio_id = "V1"
        session.add(ordine_1)
        ordine_2 = crea_ordine("ORD-2")
        ordine_2.viaggio_id = "V1"
        session.add(ordine_2)
        session.add(crea_ordine("ORD-3"))  # non su questo viaggio, non deve comparire
        session.commit()

    gestore = GestoreLogistica(session_factory)
    dettaglio = gestore.dettaglio_viaggio("V1")

    assert dettaglio.id == "V1"
    assert dettaglio.stato == "Pianificato"
    assert len(dettaglio.dipendenti) == 2
    assert [o.id for o in dettaglio.ordini] == ["ORD-1", "ORD-2"]
    assert dettaglio.ordini[0].cliente == "Cliente Test"
    assert dettaglio.ordini[0].indirizzo == "Via Test 1, Ancona"


def test_dettaglio_viaggio_senza_ordini_lista_vuota(session_factory):
    with session_factory() as session:
        crea_flotta_semplice(session, "SQ1")
        session.add(Viaggio(
            id="V1", data_partenza_prevista=datetime(2026, 7, 20, 8, 0),
            data_arrivo_prevista=datetime(2026, 7, 20, 16, 0), data_creazione=datetime.now(),
            km_percorsi=None, stato_viaggio=StatoViaggio.PIANIFICATO, composizione_id="SQ1",
        ))
        session.commit()

    gestore = GestoreLogistica(session_factory)
    dettaglio = gestore.dettaglio_viaggio("V1")

    assert dettaglio.ordini == []
    assert len(dettaglio.dipendenti) == 2
