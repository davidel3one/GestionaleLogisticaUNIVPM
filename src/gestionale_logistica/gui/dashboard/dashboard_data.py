"""Dati aggregati per la pagina Dashboard: KPI, pianificazione prossimi giorni, attivita' recente.

Nessun RF1-RF19 definisce una Dashboard: le query qui sotto leggono dai modelli esistenti
(Ordine/Viaggio/Dipendente/Camion/EsitoConsegna/Squadra), non da un "GestoreDashboard" - sono
sole letture cross-dominio composte per questa unica pagina, non una nuova capacita' di business.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    ComposizioneSquadra,
    Dipendente,
    EsitoConsegna,
    Ordine,
    Squadra,
    Viaggio,
)
from gestionale_logistica.gui.components import IconChipVariant

GIORNI_SETTIMANA = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


@dataclass
class DashboardKPI:
    ordini_ricevuti: int
    ordini_in_consegna: int
    dipendenti_disponibili: int
    dipendenti_totali: int
    camion_disponibili: int
    camion_totali: int
    ordini_consegnati_oggi: int
    trend_consegnati: str | None
    ordini_falliti_oggi: int
    trend_falliti: str | None


@dataclass
class GiornoPianificazione:
    label: str
    numero_viaggi: int


@dataclass
class VoceAttivita:
    icon_name: str
    variant: IconChipVariant
    testo: str
    tempo_relativo: str


def _inizio_giorno(riferimento: datetime) -> datetime:
    return datetime(riferimento.year, riferimento.month, riferimento.day)


def _conta_esiti(session, giorno: datetime, stato: StatoEsito) -> int:
    inizio = _inizio_giorno(giorno)
    fine = inizio + timedelta(days=1)
    return (
        session.scalar(
            select(func.count())
            .select_from(EsitoConsegna)
            .where(
                EsitoConsegna.stato_esito == stato,
                EsitoConsegna.data_registrazione >= inizio,
                EsitoConsegna.data_registrazione < fine,
            )
        )
        or 0
    )


def _formatta_trend_percentuale(oggi: int, ieri: int) -> str | None:
    """None se ieri=0 (percentuale non definita) o se il conteggio non e' cambiato."""
    if ieri == 0:
        return None
    delta_pct = round((oggi - ieri) / ieri * 100)
    if delta_pct == 0:
        return None
    freccia = "↑" if delta_pct > 0 else "↓"
    return f"{freccia} {abs(delta_pct)}% vs ieri"


def _formatta_trend_assoluto(oggi: int, ieri: int) -> str | None:
    delta = oggi - ieri
    if delta == 0:
        return None
    freccia = "↑" if delta > 0 else "↓"
    return f"{freccia} {abs(delta)} vs ieri"


def _dipendenti_impegnati(session) -> set[str]:
    """Dipendenti su una composizione attiva agganciata a un Viaggio IN_CORSO in questo momento."""
    righe = session.execute(
        select(ComposizioneSquadra.dipendente_1_id, ComposizioneSquadra.dipendente_2_id)
        .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
        .where(Viaggio.stato_viaggio == StatoViaggio.IN_CORSO)
    ).all()
    impegnati: set[str] = set()
    for dipendente_1_id, dipendente_2_id in righe:
        impegnati.add(dipendente_1_id)
        impegnati.add(dipendente_2_id)
    return impegnati


def _camion_impegnati(session) -> set[str]:
    return set(
        session.scalars(
            select(ComposizioneSquadra.camion_id)
            .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
            .where(Viaggio.stato_viaggio == StatoViaggio.IN_CORSO)
        ).all()
    )


def carica_kpi_dashboard(
    session_factory: sessionmaker = SessionLocal, ora_riferimento: datetime | None = None
) -> DashboardKPI:
    """Aggrega i 6 KPI della Dashboard.

    "Disponibile" (dipendenti/camion) = attivo e non su un Viaggio IN_CORSO in questo momento:
    assunzione dichiarata, nessun RF definisce "disponibilita'" per una risorsa - e' la lettura
    piu' letterale di "libero per un nuovo viaggio adesso" (esclude solo chi e' effettivamente
    on the road ora, non chi ha un viaggio PIANIFICATO piu' avanti).
    """
    ora_riferimento = ora_riferimento or datetime.now()
    ieri = ora_riferimento - timedelta(days=1)

    with session_factory() as session:
        ordini_ricevuti = (
            session.scalar(
                select(func.count()).select_from(Ordine).where(Ordine.stato_ordine == StatoOrdine.RICEVUTO)
            )
            or 0
        )
        ordini_in_consegna = (
            session.scalar(
                select(func.count())
                .select_from(Ordine)
                .where(Ordine.stato_ordine == StatoOrdine.IN_CONSEGNA)
            )
            or 0
        )

        dipendenti_totali = (
            session.scalar(select(func.count()).select_from(Dipendente).where(Dipendente.flg_attivo.is_(True)))
            or 0
        )
        camion_totali = (
            session.scalar(select(func.count()).select_from(Camion).where(Camion.flg_attivo.is_(True))) or 0
        )
        dipendenti_disponibili = dipendenti_totali - len(_dipendenti_impegnati(session))
        camion_disponibili = camion_totali - len(_camion_impegnati(session))

        consegnati_oggi = _conta_esiti(session, ora_riferimento, StatoEsito.COMPLETATO)
        consegnati_ieri = _conta_esiti(session, ieri, StatoEsito.COMPLETATO)
        falliti_oggi = _conta_esiti(session, ora_riferimento, StatoEsito.FALLITO)
        falliti_ieri = _conta_esiti(session, ieri, StatoEsito.FALLITO)

        return DashboardKPI(
            ordini_ricevuti=ordini_ricevuti,
            ordini_in_consegna=ordini_in_consegna,
            dipendenti_disponibili=dipendenti_disponibili,
            dipendenti_totali=dipendenti_totali,
            camion_disponibili=camion_disponibili,
            camion_totali=camion_totali,
            ordini_consegnati_oggi=consegnati_oggi,
            trend_consegnati=_formatta_trend_percentuale(consegnati_oggi, consegnati_ieri),
            ordini_falliti_oggi=falliti_oggi,
            trend_falliti=_formatta_trend_assoluto(falliti_oggi, falliti_ieri),
        )


def carica_pianificazione_prossimi_giorni(
    session_factory: sessionmaker = SessionLocal, giorni: int = 7, oggi: date | None = None
) -> list[GiornoPianificazione]:
    """Conta i Viaggio PIANIFICATO per ciascuno dei prossimi `giorni` giorni (calendario dashboard)."""
    oggi = oggi or date.today()
    with session_factory() as session:
        risultato = []
        for offset in range(giorni):
            giorno = oggi + timedelta(days=offset)
            inizio = datetime(giorno.year, giorno.month, giorno.day)
            fine = inizio + timedelta(days=1)
            numero_viaggi = (
                session.scalar(
                    select(func.count())
                    .select_from(Viaggio)
                    .where(
                        Viaggio.stato_viaggio == StatoViaggio.PIANIFICATO,
                        Viaggio.data_partenza_prevista >= inizio,
                        Viaggio.data_partenza_prevista < fine,
                    )
                )
                or 0
            )
            label = f"{GIORNI_SETTIMANA[giorno.weekday()]} {giorno.day}"
            risultato.append(GiornoPianificazione(label=label, numero_viaggi=numero_viaggi))
        return risultato


def _tempo_relativo(quando: datetime, ora_riferimento: datetime | None = None) -> str:
    """Formattazione "N min/ore/giorni fa": comportamento standard non verificabile nel mockup
    statico (mostra solo esempi gia' formattati), stesso principio gia' usato per il click sul
    backdrop del Modal."""
    ora_riferimento = ora_riferimento or datetime.now()
    minuti = int((ora_riferimento - quando).total_seconds() // 60)
    if minuti < 1:
        return "adesso"
    if minuti < 60:
        return f"{minuti} min fa"
    ore = minuti // 60
    if ore < 24:
        return "1 ora fa" if ore == 1 else f"{ore} ore fa"
    giorni = ore // 24
    return "ieri" if giorni == 1 else f"{giorni} giorni fa"


def carica_attivita_recente(
    session_factory: sessionmaker = SessionLocal, limite: int = 8
) -> list[VoceAttivita]:
    """Unisce 4 fonti di eventi reali (esiti di consegna, ordini importati, viaggi pianificati,
    squadre create), ordinate per timestamp decrescente, tenendo solo le `limite` piu' recenti."""
    with session_factory() as session:
        eventi: list[tuple[datetime, VoceAttivita]] = []

        for stato_esito, ordine_id, quando in session.execute(
            select(EsitoConsegna.stato_esito, EsitoConsegna.ordine_id, EsitoConsegna.data_registrazione)
            .order_by(EsitoConsegna.data_registrazione.desc())
            .limit(limite)
        ).all():
            if stato_esito == StatoEsito.COMPLETATO:
                eventi.append(
                    (
                        quando,
                        VoceAttivita(
                            "circle-check-big",
                            IconChipVariant.GREEN,
                            f"Consegna ordine {ordine_id} completata",
                            _tempo_relativo(quando),
                        ),
                    )
                )
            else:
                eventi.append(
                    (
                        quando,
                        VoceAttivita(
                            "triangle-alert",
                            IconChipVariant.RED,
                            f"Consegna ordine {ordine_id} fallita",
                            _tempo_relativo(quando),
                        ),
                    )
                )

        for ordine_id, quando in session.execute(
            select(Ordine.id, Ordine.data_importazione).order_by(Ordine.data_importazione.desc()).limit(limite)
        ).all():
            eventi.append(
                (
                    quando,
                    VoceAttivita(
                        "upload",
                        IconChipVariant.LIGHT_BLUE,
                        f"Ordine {ordine_id} importato da CSV",
                        _tempo_relativo(quando),
                    ),
                )
            )

        for viaggio_id, quando in session.execute(
            select(Viaggio.id, Viaggio.data_creazione).order_by(Viaggio.data_creazione.desc()).limit(limite)
        ).all():
            eventi.append(
                (
                    quando,
                    VoceAttivita(
                        "calendar",
                        IconChipVariant.BLUE,
                        f"Viaggio {viaggio_id} pianificato",
                        _tempo_relativo(quando),
                    ),
                )
            )

        for squadra_id, quando in session.execute(
            select(Squadra.id, Squadra.data_creazione).order_by(Squadra.data_creazione.desc()).limit(limite)
        ).all():
            eventi.append(
                (
                    quando,
                    VoceAttivita(
                        "users",
                        IconChipVariant.BLUE,
                        f"Nuova squadra {squadra_id} aggiunta",
                        _tempo_relativo(quando),
                    ),
                )
            )

        eventi.sort(key=lambda coppia: coppia[0], reverse=True)
        return [voce for _, voce in eventi[:limite]]
