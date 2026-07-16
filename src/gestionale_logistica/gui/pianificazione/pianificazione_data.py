"""Dati per la pagina Pianificazione: le 3 tab (RF13 Automatica, RF10/RF11 Manuale, RF12
Assistita) leggono da qui — composizioni/ordini candidati per la data selezionata, proiezione di
un `PianoGiornaliero` calcolato (RF13) e stato di un viaggio in composizione (RF10/RF11/RF12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import StatoOrdine
from gestionale_logistica.database.models import ComposizioneSquadra, Ordine, Viaggio
from gestionale_logistica.gui.pianificazione.components import (
    CATEGORIA_BADGE_LABELS,
    RigaOrdineComposizione,
    RigaOrdineSuggerito,
)
from gestionale_logistica.ottimizzazione.motore_ottimizzazione import PianoGiornaliero, SuggerimentoOrdini


def _composizioni_disponibili(session: Session, giorno: date) -> list[ComposizioneSquadra]:
    """Composizioni attive, valide e non ancora occupate nel giorno indicato: stessa logica di
    filtro di `MotoreOttimizzazione.calcola_piano`, duplicata qui in sola lettura (nessun metodo
    di sola lettura equivalente è esposto da `GestoreLogistica`/`MotoreOttimizzazione`)."""
    composizioni = [
        c
        for c in session.scalars(
            select(ComposizioneSquadra).where(ComposizioneSquadra.flg_attiva.is_(True))
        )
        if c.data_inizio_validita.date() <= giorno
        and (c.data_fine_validita is None or c.data_fine_validita.date() >= giorno)
    ]
    inizio_giorno = datetime(giorno.year, giorno.month, giorno.day)
    fine_giorno = inizio_giorno + timedelta(days=1)
    occupate = set(
        session.scalars(
            select(Viaggio.composizione_id).where(
                Viaggio.data_partenza_prevista >= inizio_giorno,
                Viaggio.data_partenza_prevista < fine_giorno,
            )
        )
    )
    return [c for c in composizioni if c.id_composizione not in occupate]


def conta_composizioni_disponibili(giorno: date, session_factory: sessionmaker = SessionLocal) -> int:
    """Testo di supporto del Filter Bar ("N composizioni attive disponibili per il ...")."""
    with session_factory() as session:
        return len(_composizioni_disponibili(session, giorno))


def descrizione_composizioni_disponibili(
    giorno: date, session_factory: sessionmaker = SessionLocal
) -> str:
    """Stessa label di supporto del Filter Bar di Automatica ("N composizioni attive disponibili
    per il ..."), riusata anche dall'Avvio Card di Assistita/Manuale (deviazione dal mockup,
    che non la modella lì — richiesta esplicita dell'utente 2026-07-16 per coerenza fra le 3 tab)."""
    numero = conta_composizioni_disponibili(giorno, session_factory)
    etichetta = "composizione attiva" if numero == 1 else "composizioni attive"
    return f"{numero} {etichetta} disponibili per il {giorno.strftime('%d/%m/%Y')}"


def elenca_composizioni_disponibili(
    giorno: date, session_factory: sessionmaker = SessionLocal
) -> list[tuple[str, str]]:
    """(composizione_id, "Composizione: #N") per il campo di selezione dell'Avvio Card."""
    with session_factory() as session:
        return [
            (c.id_composizione, f"Composizione: #{c.squadra_id}")
            for c in _composizioni_disponibili(session, giorno)
        ]


def elenca_ordini_candidati(
    session_factory: sessionmaker = SessionLocal,
) -> list[RigaOrdineComposizione]:
    """Righe per la tabella "Aggiungi ordine" della Composizione Card: tutti gli ordini RICEVUTO
    non ancora assegnati a un viaggio — l'idoneità/capacità è verificata al momento dell'aggiunta
    (RF11, `GestoreLogistica.aggiungi_ordine_a_viaggio`), non qui."""
    with session_factory() as session:
        ordini = session.scalars(
            select(Ordine).where(Ordine.stato_ordine == StatoOrdine.RICEVUTO, Ordine.viaggio_id.is_(None))
        )
        return [
            RigaOrdineComposizione(
                ordine_id=o.id,
                cliente=o.cliente,
                peso=o.peso,
                volume=o.volume_cargo,
                categoria_label=CATEGORIA_BADGE_LABELS.get(o.categoria_consegna.value, "Standard"),
            )
            for o in ordini
        ]


@dataclass
class StatoComposizioneViaggio:
    squadra_label: str
    camion_label: str
    partenza_label: str
    peso_occupato: float
    peso_massimo: float
    volume_occupato: float
    volume_massimo: float
    righe_ordini: list[RigaOrdineComposizione]


def costruisci_stato_composizione(
    viaggio_id: str, session_factory: sessionmaker = SessionLocal
) -> StatoComposizioneViaggio | None:
    """Proietta un `Viaggio` IN_COMPOSIZIONE (RF10) nello stato mostrato dalla Composizione Card."""
    with session_factory() as session:
        viaggio = session.get(Viaggio, viaggio_id)
        if viaggio is None:
            return None
        composizione = viaggio.composizione
        camion = composizione.camion
        ordini = list(viaggio.ordini)

        return StatoComposizioneViaggio(
            squadra_label=f"#{composizione.squadra_id}",
            camion_label=f"Camion {camion.targa} ({camion.tipo_mezzo})",
            partenza_label=viaggio.data_partenza_prevista.strftime("%d/%m %H:%M"),
            peso_occupato=sum(o.peso for o in ordini),
            peso_massimo=camion.peso_massimo,
            volume_occupato=sum(o.volume_cargo for o in ordini),
            volume_massimo=camion.volume_massimo,
            righe_ordini=[
                RigaOrdineComposizione(
                    ordine_id=o.id,
                    cliente=o.cliente,
                    peso=o.peso,
                    volume=o.volume_cargo,
                    categoria_label=CATEGORIA_BADGE_LABELS.get(o.categoria_consegna.value, "Standard"),
                )
                for o in ordini
            ],
        )


@dataclass
class RigaViaggioProposto:
    composizione_id: str
    squadra_label: str
    numero_ordini: int
    partenza_label: str
    arrivo_label: str
    capacita_percentuale: float


def costruisci_righe_piano(
    piano: PianoGiornaliero,
    ora_partenza: datetime,
    durata_viaggio: timedelta,
    session_factory: sessionmaker = SessionLocal,
) -> list[RigaViaggioProposto]:
    """Proietta le assegnazioni di un `PianoGiornaliero` (calcolato ma non ancora applicato) in
    righe per la Proposed Trips Table. La percentuale di "CAPACITÀ" è il maggiore tra peso% e
    volume% occupati (il collo di bottiglia del viaggio): il mockup mostra una sola percentuale
    per riga senza specificarne la formula — assunzione dichiarata, nessun RF la definisce."""
    if not piano.assegnazioni:
        return []

    arrivo = ora_partenza + durata_viaggio
    with session_factory() as session:
        composizioni_ids = [a.composizione_id for a in piano.assegnazioni]
        composizioni = {
            c.id_composizione: c
            for c in session.scalars(
                select(ComposizioneSquadra).where(
                    ComposizioneSquadra.id_composizione.in_(composizioni_ids)
                )
            )
        }
        tutti_ordini_ids = [ordine_id for a in piano.assegnazioni for ordine_id in a.ordini_ids]
        ordini = {
            o.id: o for o in session.scalars(select(Ordine).where(Ordine.id.in_(tutti_ordini_ids)))
        }

        righe: list[RigaViaggioProposto] = []
        for assegnazione in piano.assegnazioni:
            composizione = composizioni.get(assegnazione.composizione_id)
            if composizione is None:
                continue
            camion = composizione.camion
            ordini_viaggio = [ordini[oid] for oid in assegnazione.ordini_ids if oid in ordini]

            peso_pct = (
                sum(o.peso for o in ordini_viaggio) / camion.peso_massimo * 100
                if camion.peso_massimo
                else 0.0
            )
            volume_pct = (
                sum(o.volume_cargo for o in ordini_viaggio) / camion.volume_massimo * 100
                if camion.volume_massimo
                else 0.0
            )

            righe.append(
                RigaViaggioProposto(
                    composizione_id=assegnazione.composizione_id,
                    squadra_label=f"#{composizione.squadra_id}",
                    numero_ordini=len(ordini_viaggio),
                    partenza_label=ora_partenza.strftime("%d/%m %H:%M"),
                    arrivo_label=arrivo.strftime("%d/%m %H:%M"),
                    capacita_percentuale=max(peso_pct, volume_pct),
                )
            )
        return righe


@dataclass
class DettaglioViaggioProposto:
    squadra_label: str
    camion_label: str
    partenza_label: str
    arrivo_label: str
    righe_ordini: list[RigaOrdineComposizione]


def costruisci_dettaglio_viaggio_proposto(
    piano: PianoGiornaliero,
    composizione_id: str,
    ora_partenza: datetime,
    durata_viaggio: timedelta,
    session_factory: sessionmaker = SessionLocal,
) -> DettaglioViaggioProposto | None:
    """Proietta una singola assegnazione di un `PianoGiornaliero` (calcolato ma non ancora
    applicato, quindi non ancora un `Viaggio` in database) nel dettaglio ordini mostrato dal
    modale "espandi riga" della Proposed Trips Table (chevron, RF13)."""
    assegnazione = next(
        (a for a in piano.assegnazioni if a.composizione_id == composizione_id), None
    )
    if assegnazione is None:
        return None
    with session_factory() as session:
        composizione = session.get(ComposizioneSquadra, composizione_id)
        if composizione is None:
            return None
        camion = composizione.camion
        ordini = session.scalars(select(Ordine).where(Ordine.id.in_(assegnazione.ordini_ids)))
        return DettaglioViaggioProposto(
            squadra_label=f"#{composizione.squadra_id}",
            camion_label=f"Camion {camion.targa} ({camion.tipo_mezzo})",
            partenza_label=ora_partenza.strftime("%d/%m %H:%M"),
            arrivo_label=(ora_partenza + durata_viaggio).strftime("%d/%m %H:%M"),
            righe_ordini=[
                RigaOrdineComposizione(
                    ordine_id=o.id,
                    cliente=o.cliente,
                    peso=o.peso,
                    volume=o.volume_cargo,
                    categoria_label=CATEGORIA_BADGE_LABELS.get(o.categoria_consegna.value, "Standard"),
                )
                for o in ordini
            ],
        )


def costruisci_righe_suggerimento(
    suggerimento: SuggerimentoOrdini, session_factory: sessionmaker = SessionLocal
) -> list[RigaOrdineSuggerito]:
    """Proietta i soli id di `MotoreOttimizzazione.suggerisci_ordini` (RF12) in righe con i
    dettagli mostrati dalla `SuggestionSection` (cliente/peso/volume/categoria)."""
    if not suggerimento.ordini_suggeriti:
        return []
    with session_factory() as session:
        ordini = session.scalars(
            select(Ordine).where(Ordine.id.in_(suggerimento.ordini_suggeriti))
        )
        return [
            RigaOrdineSuggerito(
                ordine_id=o.id,
                cliente=o.cliente,
                peso=o.peso,
                volume=o.volume_cargo,
                categoria_label=CATEGORIA_BADGE_LABELS.get(o.categoria_consegna.value, "Standard"),
            )
            for o in ordini
        ]
