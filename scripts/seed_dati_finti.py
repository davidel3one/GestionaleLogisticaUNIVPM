"""Popola gestionale.db con dati finti realistici per testare a schermo la GUI (Dashboard).

Rilanciabile: se trova dipendenti gia' presenti assume che il DB sia gia' stato seedato in un
run precedente e si limita a ristampare il riepilogo, senza tentare nuovi inserimenti.
"""

import itertools
import random
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from gestionale_logistica.database.base import Base, SessionLocal, engine
from gestionale_logistica.database.enums import CategoriaConsegna, StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    CausaleFallimento,
    Camion,
    ComposizioneSquadra,
    Dipendente,
    EsitoConsegna,
    Ordine,
    RegistroEsiti,
    Viaggio,
)
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica
from gestionale_logistica.risorse.gestore_camion import GestoreCamion
from gestionale_logistica.risorse.gestore_dipendenti import GestoreDipendenti
from gestionale_logistica.risorse.gestore_squadre import GestoreSquadre

NOMI = [
    "Marco", "Luca", "Andrea", "Matteo", "Simone", "Francesco", "Alessandro", "Davide",
    "Fabio", "Giulia", "Chiara", "Elisa", "Sara", "Martina", "Federica", "Valentina",
    "Silvia", "Elena", "Giorgio", "Paolo", "Roberto", "Stefano", "Michele", "Antonio",
]
COGNOMI = [
    "Rossi", "Bianchi", "Ferrari", "Russo", "Esposito", "Romano", "Colombo", "Ricci",
    "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Costa", "Giordano",
    "Mancini", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Fontana", "Santoro", "Mariani",
]
COMUNI_MARCHE = [
    ("Ancona", "AN"), ("Pesaro", "PU"), ("Senigallia", "AN"), ("Jesi", "AN"), ("Fano", "PU"),
    ("Macerata", "MC"), ("Fermo", "FM"), ("Ascoli Piceno", "AP"), ("Urbino", "PU"),
    ("Osimo", "AN"), ("Civitanova Marche", "MC"), ("Recanati", "MC"), ("Fabriano", "AN"),
]
VIE = ["Roma", "Garibaldi", "Marconi", "Dante Alighieri", "Mazzini", "Cavour", "IV Novembre", "Trieste", "Aldo Moro", "Kennedy"]
NEGOZI = ["Unieuro", "MediaWorld", "Expert"]
CATEGORIE_STANDARD = [
    CategoriaConsegna.BORDO_STRADA,
    CategoriaConsegna.INSTALLAZIONE_SEMPLICE_AL_PIANO,
    CategoriaConsegna.INCASSO,
]
CATEGORIE_TUTTE = CATEGORIE_STANDARD + [CategoriaConsegna.BIG, CategoriaConsegna.CERTIFICAZIONE_GAS]

_contatore_ordini = itertools.count(1)


def nuovo_id_ordine() -> str:
    return f"ORD-{next(_contatore_ordini):04d}"


def cf_fittizio(i: int) -> str:
    lettera = chr(65 + i % 26)
    return f"TSTFTZ{i:02d}A01H501{lettera}"


def genera_peso_volume(categoria: CategoriaConsegna) -> tuple[float, float]:
    if categoria == CategoriaConsegna.BIG:
        return round(random.uniform(60, 220), 1), round(random.uniform(0.8, 2.5), 2)
    return round(random.uniform(4, 45), 1), round(random.uniform(0.05, 0.6), 2)


def crea_ordine(session: Session, categoria: CategoriaConsegna, data_importazione: datetime) -> str:
    comune, provincia = random.choice(COMUNI_MARCHE)
    peso, volume = genera_peso_volume(categoria)
    id_ = nuovo_id_ordine()
    session.add(
        Ordine(
            id=id_,
            indirizzo=f"Via {random.choice(VIE)} {random.randint(1, 150)}",
            comune=comune,
            provincia=provincia,
            lat=None,
            lon=None,
            cliente=f"{random.choice(NOMI)} {random.choice(COGNOMI)}",
            peso=peso,
            volume_cargo=volume,
            categoria_consegna=categoria,
            stato_ordine=StatoOrdine.RICEVUTO,
            data_importazione=data_importazione,
            data_consegna=None,
            viaggio_id=None,
            negozio_partner=random.choice(NEGOZI),
        )
    )
    return id_


def crea_storico_giorno(
    giorno,
    n_completati: int,
    n_falliti: int,
    codici_causali: list[str],
    composizioni_ids: list[str],
) -> None:
    """Crea un RegistroEsiti + N EsitoConsegna con data_registrazione esplicita per 'giorno',
    ognuno agganciato a un Ordine/Viaggio storici (Viaggio COMPLETATO) creati direttamente via ORM,
    perche' GestoreRendicontazione.registra_esito fissa sempre data_registrazione=now()."""
    mezzanotte = datetime(giorno.year, giorno.month, giorno.day)
    with SessionLocal() as session:
        registro = RegistroEsiti(data_riferimento=mezzanotte)
        session.add(registro)
        session.flush()

        viaggi_storici = []
        for i in range(4):
            ora_partenza = datetime(giorno.year, giorno.month, giorno.day, random.choice([7, 8, 9]))
            viaggio_id = f"V-STORICO-{giorno:%Y%m%d}-{i + 1:02d}"
            session.add(
                Viaggio(
                    id=viaggio_id,
                    data_partenza_prevista=ora_partenza,
                    data_arrivo_prevista=ora_partenza + timedelta(hours=8),
                    data_creazione=ora_partenza - timedelta(hours=2),
                    km_percorsi=round(random.uniform(20, 180), 1),
                    stato_viaggio=StatoViaggio.COMPLETATO,
                    composizione_id=random.choice(composizioni_ids),
                )
            )
            viaggi_storici.append(viaggio_id)
        session.flush()

        esiti_da_creare = [StatoEsito.COMPLETATO] * n_completati + [StatoEsito.FALLITO] * n_falliti
        random.shuffle(esiti_da_creare)

        for stato_esito in esiti_da_creare:
            categoria = random.choice(CATEGORIE_STANDARD)
            comune, provincia = random.choice(COMUNI_MARCHE)
            peso, volume = genera_peso_volume(categoria)
            viaggio_id = random.choice(viaggi_storici)
            ordine_id = nuovo_id_ordine()
            ora_evento = datetime(giorno.year, giorno.month, giorno.day, random.randint(8, 19), random.randint(0, 59))

            session.add(
                Ordine(
                    id=ordine_id,
                    indirizzo=f"Via {random.choice(VIE)} {random.randint(1, 150)}",
                    comune=comune,
                    provincia=provincia,
                    lat=None,
                    lon=None,
                    cliente=f"{random.choice(NOMI)} {random.choice(COGNOMI)}",
                    peso=peso,
                    volume_cargo=volume,
                    categoria_consegna=categoria,
                    stato_ordine=StatoOrdine.COMPLETATO if stato_esito == StatoEsito.COMPLETATO else StatoOrdine.FALLITO,
                    data_importazione=mezzanotte - timedelta(days=2),
                    data_consegna=ora_evento,
                    viaggio_id=viaggio_id,
                    negozio_partner=random.choice(NEGOZI),
                )
            )
            session.add(
                EsitoConsegna(
                    stato_esito=stato_esito,
                    data_registrazione=ora_evento,
                    ordine_id=ordine_id,
                    viaggio_id=viaggio_id,
                    causale_id=random.choice(codici_causali) if stato_esito == StatoEsito.FALLITO else None,
                    registro_id=registro.id,
                )
            )

        session.commit()


def stampa_riepilogo(session) -> None:
    print("\n=== Riepilogo dati seed ===")

    print("Ordini per stato:")
    for stato in StatoOrdine:
        n = session.scalar(select(func.count()).select_from(Ordine).where(Ordine.stato_ordine == stato))
        print(f"  {stato.value}: {n}")

    print("Viaggi per stato:")
    for stato in StatoViaggio:
        n = session.scalar(select(func.count()).select_from(Viaggio).where(Viaggio.stato_viaggio == stato))
        print(f"  {stato.value}: {n}")

    dipendenti_attivi = session.scalar(
        select(func.count()).select_from(Dipendente).where(Dipendente.flg_attivo.is_(True))
    )
    dipendenti_occupati = session.scalar(
        select(func.count(func.distinct(Dipendente.id)))
        .select_from(Dipendente)
        .join(
            ComposizioneSquadra,
            or_(
                ComposizioneSquadra.dipendente_1_id == Dipendente.id,
                ComposizioneSquadra.dipendente_2_id == Dipendente.id,
            ),
        )
        .where(ComposizioneSquadra.flg_attiva.is_(True))
    )
    print(f"Dipendenti attivi: {dipendenti_attivi} (occupati: {dipendenti_occupati}, liberi: {dipendenti_attivi - dipendenti_occupati})")

    camion_attivi = session.scalar(select(func.count()).select_from(Camion).where(Camion.flg_attivo.is_(True)))
    camion_occupati = session.scalar(
        select(func.count(func.distinct(Camion.id)))
        .select_from(Camion)
        .join(ComposizioneSquadra, ComposizioneSquadra.camion_id == Camion.id)
        .where(ComposizioneSquadra.flg_attiva.is_(True))
    )
    print(f"Camion attivi: {camion_attivi} (occupati: {camion_occupati}, liberi: {camion_attivi - camion_occupati})")

    oggi = datetime.now().date()
    ieri = oggi - timedelta(days=1)
    for etichetta, giorno in (("Oggi", oggi), ("Ieri", ieri)):
        inizio = datetime(giorno.year, giorno.month, giorno.day)
        fine = inizio + timedelta(days=1)
        completati = session.scalar(
            select(func.count())
            .select_from(EsitoConsegna)
            .where(
                EsitoConsegna.data_registrazione >= inizio,
                EsitoConsegna.data_registrazione < fine,
                EsitoConsegna.stato_esito == StatoEsito.COMPLETATO,
            )
        )
        falliti = session.scalar(
            select(func.count())
            .select_from(EsitoConsegna)
            .where(
                EsitoConsegna.data_registrazione >= inizio,
                EsitoConsegna.data_registrazione < fine,
                EsitoConsegna.stato_esito == StatoEsito.FALLITO,
            )
        )
        print(f"Esiti {etichetta} ({giorno}): completati={completati}, falliti={falliti}")


def main() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        if session.scalar(select(func.count()).select_from(Dipendente)) > 0:
            print("Database gia' popolato da un run precedente: salto il seeding.")
            stampa_riepilogo(session)
            return

    random.seed(42)
    ora = datetime.now()

    gestore_dipendenti = GestoreDipendenti()
    gestore_camion = GestoreCamion()
    gestore_squadre = GestoreSquadre()
    gestore_logistica = GestoreLogistica()

    # 1. 24 dipendenti, 4 con certificazione gas
    for i in range(1, 25):
        gestore_dipendenti.inserisci_dipendente(
            f"EMP-{i:02d}",
            NOMI[(i - 1) % len(NOMI)],
            COGNOMI[(i * 7 - 1) % len(COGNOMI)],
            cf_fittizio(i),
            data_assunzione=ora - timedelta(days=random.randint(60, 2000)),
            flg_certificazione_gas=i <= 4,
        )

    # 2. 12 camion, 4 con sponda idraulica
    for i in range(1, 13):
        gestore_camion.inserisci_camion(
            f"CAM-{i:02d}",
            targa=f"AB{100 + i:03d}CD",
            tipo_mezzo=random.choice(["Furgone", "Camion", "Bilico"]),
            data_acquisizione=ora - timedelta(days=random.randint(100, 1500)),
            peso_massimo=round(random.uniform(1500, 8000), 0),
            volume_massimo=round(random.uniform(15, 45), 1),
            flg_sponda_idraulica=i <= 4,
        )

    # 3. 8 squadre con composizione attiva: usano EMP-01..16 e CAM-01..08, lasciando
    # EMP-17..24 e CAM-09..12 liberi (mai assegnati)
    composizioni_ids = []
    for i in range(1, 9):
        squadra_id = f"SQ-{i:02d}"
        comp_id = f"COMP-{i:02d}"
        gestore_squadre.crea_squadra(squadra_id, data_creazione=ora - timedelta(days=random.randint(30, 900)))
        gestore_squadre.apri_composizione(
            comp_id,
            squadra_id,
            camion_id=f"CAM-{i:02d}",
            dipendente_1_id=f"EMP-{2 * i - 1:02d}",
            dipendente_2_id=f"EMP-{2 * i:02d}",
            data_inizio_validita=ora - timedelta(days=random.randint(30, 900)),
        )
        composizioni_ids.append(comp_id)

    # CAM-01..04 hanno la sponda idraulica -> COMP-01..04 idonee a Big.
    # EMP-01..04 hanno la certificazione gas (agganciati a SQ-01/SQ-02) -> COMP-01/02 idonee a CertificazioneGas.
    comp_big = {"COMP-01", "COMP-02", "COMP-03", "COMP-04"}
    comp_gas = {"COMP-01", "COMP-02"}

    # 4. 20 ordini RICEVUTO liberi (mai agganciati a un viaggio), mix di tutte le categorie
    with SessionLocal() as session:
        for _ in range(20):
            crea_ordine(session, random.choice(CATEGORIE_TUTTE), ora - timedelta(hours=random.randint(1, 72)))
        session.commit()

    # 5. Viaggi pianificati nei prossimi 7 giorni (weekend con meno viaggi)
    conteggio_per_offset = {1: 2, 2: 2, 3: 1, 4: 1, 5: 2, 6: 2, 7: 2}
    indice_comp = 0
    for offset, n_viaggi in conteggio_per_offset.items():
        giorno = ora + timedelta(days=offset)
        for _ in range(n_viaggi):
            comp_id = composizioni_ids[indice_comp % len(composizioni_ids)]
            indice_comp += 1
            ora_partenza = datetime(giorno.year, giorno.month, giorno.day, random.choice([7, 8, 9]))
            risultato_viaggio = gestore_logistica.avvia_composizione_viaggio(comp_id, ora_partenza)
            if not risultato_viaggio.ok:
                continue

            categorie_ammesse = list(CATEGORIE_STANDARD)
            if comp_id in comp_big:
                categorie_ammesse.append(CategoriaConsegna.BIG)
            if comp_id in comp_gas:
                categorie_ammesse.append(CategoriaConsegna.CERTIFICAZIONE_GAS)

            with SessionLocal() as session:
                nuovi_ordini_ids = [
                    crea_ordine(session, random.choice(categorie_ammesse), ora - timedelta(hours=random.randint(1, 48)))
                    for _ in range(random.choice([1, 2]))
                ]
                session.commit()

            for ordine_id in nuovi_ordini_ids:
                gestore_logistica.aggiungi_ordine_a_viaggio(risultato_viaggio.viaggio_id, ordine_id)
            gestore_logistica.chiudi_composizione_viaggio(risultato_viaggio.viaggio_id)

    # 6a. Viaggi "in transito": partenza gia' avvenuta oggi, poi verifica_partenze li porta a IN_CORSO
    # (e i loro ordini IN_CONSEGNA) -> genera gli 8-10 ordini IN_CONSEGNA richiesti.
    for i in range(4):
        comp_id = composizioni_ids[i]
        ora_partenza = ora - timedelta(hours=random.randint(2, 6))
        risultato_viaggio = gestore_logistica.avvia_composizione_viaggio(comp_id, ora_partenza)
        if not risultato_viaggio.ok:
            continue

        categorie_ammesse = list(CATEGORIE_STANDARD)
        if comp_id in comp_big:
            categorie_ammesse.append(CategoriaConsegna.BIG)

        with SessionLocal() as session:
            nuovi_ordini_ids = [
                crea_ordine(session, random.choice(categorie_ammesse), ora - timedelta(hours=random.randint(1, 24)))
                for _ in range(2)
            ]
            session.commit()

        for ordine_id in nuovi_ordini_ids:
            gestore_logistica.aggiungi_ordine_a_viaggio(risultato_viaggio.viaggio_id, ordine_id)
        gestore_logistica.chiudi_composizione_viaggio(risultato_viaggio.viaggio_id)

    gestore_logistica.verifica_partenze(ora_riferimento=ora)

    # 6b. Storico "oggi vs ieri" per il trend della dashboard
    causali = [
        CausaleFallimento(codice="IND_ERRATO", descrizione="Indirizzo non raggiungibile"),
        CausaleFallimento(codice="CLIENTE_ASSENTE", descrizione="Cliente assente alla consegna"),
        CausaleFallimento(codice="MERCE_DANNEGGIATA", descrizione="Merce danneggiata durante il trasporto"),
    ]
    with SessionLocal() as session:
        session.add_all(causali)
        session.commit()
        codici_causali = [c.codice for c in causali]

    crea_storico_giorno(ora.date(), n_completati=13, n_falliti=3, codici_causali=codici_causali, composizioni_ids=composizioni_ids)
    crea_storico_giorno((ora - timedelta(days=1)).date(), n_completati=11, n_falliti=2, codici_causali=codici_causali, composizioni_ids=composizioni_ids)

    with SessionLocal() as session:
        stampa_riepilogo(session)


if __name__ == "__main__":
    main()
