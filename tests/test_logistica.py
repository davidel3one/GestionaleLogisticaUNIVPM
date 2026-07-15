from datetime import datetime, timedelta

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Ordine, Squadra, Viaggio
from gestionale_logistica.logistica.gestore_logistica import (
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
