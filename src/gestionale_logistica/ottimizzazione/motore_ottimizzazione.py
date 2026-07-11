import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import pulp
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Ordine, Viaggio
from gestionale_logistica.ottimizzazione.clustering import raggruppa_ordini
from gestionale_logistica.ottimizzazione.stima_durata import (
    SOGLIA_NODI_HELD_KARP,
    stima_durata_viaggio,
    tour_esatto,
    tour_euristico,
)

LIMITE_RNF4_SECONDI = 180.0
QUOTA_BUDGET_PRIMA_DI_FORZARE_EURISTICO = 0.6
MINIMO_TIME_LIMIT_KNAPSACK_SECONDI = 1.0


def _time_limit_residuo(inizio_esecuzione: float) -> float:
    """TimeLimit (secondi) da passare al solve CBC del knapsack per cluster.

    Pari al tempo rimanente sul budget RNF4 totale di 180s, con un minimo
    pratico di MINIMO_TIME_LIMIT_KNAPSACK_SECONDI: non esiste una variante
    euristica del knapsack di capacita' in questo codice (l'euristico
    riguarda solo la costruzione del tour), quindi anche a budget quasi
    esaurito si tenta comunque un solve breve invece di saltare il cluster.
    """
    tempo_trascorso = time.perf_counter() - inizio_esecuzione
    return max(MINIMO_TIME_LIMIT_KNAPSACK_SECONDI, LIMITE_RNF4_SECONDI - tempo_trascorso)


@dataclass
class SuggerimentoOrdini:
    ordini_suggeriti: list[str]
    peso_utilizzato: float
    volume_utilizzato: float
    peso_disponibile: float
    volume_disponibile: float


@dataclass
class AssegnazioneViaggio:
    composizione_id: str
    ordini_ids: list[str]


@dataclass
class PianoGiornaliero:
    assegnazioni: list[AssegnazioneViaggio]
    ordini_non_assegnati: list[str]


@dataclass
class RisultatoPianificazione:
    viaggi_creati: list[str]
    ordini_assegnati: int


class MotoreOttimizzazione:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def _ordine_idoneo(self, ordine: Ordine, camion: Camion, dipendenti: list[Dipendente]) -> bool:
        if ordine.categoria_consegna == CategoriaConsegna.BIG:
            return camion.flg_sponda_idraulica
        if ordine.categoria_consegna == CategoriaConsegna.CERTIFICAZIONE_GAS:
            return any(dipendente.flg_certificazione_gas for dipendente in dipendenti)
        return True

    def suggerisci_ordini(self, viaggio_id: str) -> SuggerimentoOrdini:
        with self.session_factory() as session:
            viaggio = session.get(Viaggio, viaggio_id)
            composizione = viaggio.composizione
            camion = composizione.camion
            dipendenti = [composizione.dipendente_1, composizione.dipendente_2]

            peso_occupato = sum(ordine.peso for ordine in viaggio.ordini)
            volume_occupato = sum(ordine.volume_cargo for ordine in viaggio.ordini)
            peso_residuo = camion.peso_massimo - peso_occupato
            volume_residuo = camion.volume_massimo - volume_occupato

            candidati = list(
                session.scalars(
                    select(Ordine).where(
                        Ordine.stato_ordine == StatoOrdine.RICEVUTO,
                        Ordine.viaggio_id.is_(None),
                    )
                )
            )
            candidati = [o for o in candidati if self._ordine_idoneo(o, camion, dipendenti)]

            if not candidati:
                return SuggerimentoOrdini(
                    ordini_suggeriti=[],
                    peso_utilizzato=peso_occupato,
                    volume_utilizzato=volume_occupato,
                    peso_disponibile=camion.peso_massimo,
                    volume_disponibile=camion.volume_massimo,
                )

            problema = pulp.LpProblem("suggerisci_ordini", pulp.LpMaximize)
            x = {ordine.id: pulp.LpVariable(f"x_{ordine.id}", cat="Binary") for ordine in candidati}

            problema += pulp.lpSum(x.values())
            problema += pulp.lpSum(ordine.peso * x[ordine.id] for ordine in candidati) <= peso_residuo
            problema += (
                pulp.lpSum(ordine.volume_cargo * x[ordine.id] for ordine in candidati) <= volume_residuo
            )

            problema.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=LIMITE_RNF4_SECONDI))

            scelti = [ordine for ordine in candidati if x[ordine.id].value() == 1]

            return SuggerimentoOrdini(
                ordini_suggeriti=[ordine.id for ordine in scelti],
                peso_utilizzato=peso_occupato + sum(ordine.peso for ordine in scelti),
                volume_utilizzato=volume_occupato + sum(ordine.volume_cargo for ordine in scelti),
                peso_disponibile=camion.peso_massimo,
                volume_disponibile=camion.volume_massimo,
            )

    def calcola_piano(
        self,
        ora_partenza: datetime,
        composizione_ids: list[str] | None = None,
        durata_viaggio: timedelta = timedelta(hours=8),
    ) -> PianoGiornaliero:
        inizio_esecuzione = time.perf_counter()
        budget_esecuzione_secondi = LIMITE_RNF4_SECONDI * QUOTA_BUDGET_PRIMA_DI_FORZARE_EURISTICO
        giorno = ora_partenza.date()

        with self.session_factory() as session:
            query = select(ComposizioneSquadra).where(ComposizioneSquadra.flg_attiva.is_(True))
            if composizione_ids is not None:
                query = query.where(ComposizioneSquadra.id_composizione.in_(composizione_ids))

            composizioni = [
                composizione
                for composizione in session.scalars(query)
                if composizione.data_inizio_validita.date() <= giorno
                and (
                    composizione.data_fine_validita is None
                    or composizione.data_fine_validita.date() >= giorno
                )
            ]

            inizio_giorno = datetime(giorno.year, giorno.month, giorno.day)
            fine_giorno = inizio_giorno + timedelta(days=1)
            composizioni_occupate = set(
                session.scalars(
                    select(Viaggio.composizione_id).where(
                        Viaggio.data_partenza_prevista >= inizio_giorno,
                        Viaggio.data_partenza_prevista < fine_giorno,
                    )
                )
            )
            composizioni = [c for c in composizioni if c.id_composizione not in composizioni_occupate]

            tutti_candidati = list(
                session.scalars(
                    select(Ordine).where(
                        Ordine.stato_ordine == StatoOrdine.RICEVUTO,
                        Ordine.viaggio_id.is_(None),
                    )
                )
            )

            if not composizioni or not tutti_candidati:
                return PianoGiornaliero(
                    assegnazioni=[], ordini_non_assegnati=[ordine.id for ordine in tutti_candidati]
                )

            composizioni_by_id = {c.id_composizione: c for c in composizioni}

            candidati_idonei = [
                ordine
                for ordine in tutti_candidati
                if any(
                    self._ordine_idoneo(
                        ordine, comp.camion, [comp.dipendente_1, comp.dipendente_2]
                    )
                    for comp in composizioni
                )
            ]

            if not candidati_idonei:
                return PianoGiornaliero(
                    assegnazioni=[], ordini_non_assegnati=[ordine.id for ordine in tutti_candidati]
                )

            ordini_by_id = {ordine.id: ordine for ordine in candidati_idonei}

            cluster_ordini = raggruppa_ordini(candidati_idonei)
            # Cluster piu' numerosi elaborati per primi: consolida gli ordini
            # vicini sullo stesso viaggio prima di dedicare una composizione
            # intera a un singolo punto isolato. Scelta non specificata
            # esplicitamente nel brief, ma coerente con l'obiettivo RF13 di
            # preferire raggruppamenti compatti quando piu' composizioni sono
            # disponibili (altrimenti l'assegnazione dipenderebbe solo
            # dall'ordine arbitrario restituito da DBSCAN).
            cluster_ordini.sort(key=len, reverse=True)

            composizioni_disponibili = list(composizioni)
            assegnazioni: list[AssegnazioneViaggio] = []
            ordini_assegnati_ids: set[str] = set()
            ordini_isolati_non_serviti: list[Ordine] = []

            for cluster in cluster_ordini:
                ordini_restanti_cluster = list(cluster)

                for composizione in list(composizioni_disponibili):
                    if not ordini_restanti_cluster:
                        break

                    camion = composizione.camion
                    dipendenti = [composizione.dipendente_1, composizione.dipendente_2]
                    idonei = [
                        ordine
                        for ordine in ordini_restanti_cluster
                        if self._ordine_idoneo(ordine, camion, dipendenti)
                    ]
                    if not idonei:
                        continue

                    subset = self._knapsack_capacita_massima(
                        idonei, camion, _time_limit_residuo(inizio_esecuzione)
                    )
                    if subset is None:
                        logging.warning(
                            "calcola_piano: solver non ottimale per la composizione %s "
                            "(cluster di %d ordini) - trattato come non risolvibile in questa esecuzione",
                            composizione.id_composizione,
                            len(idonei),
                        )
                        continue
                    if not subset:
                        continue

                    forza_euristico = (
                        time.perf_counter() - inizio_esecuzione
                    ) > budget_esecuzione_secondi
                    subset = self._applica_vincolo_durata(subset, durata_viaggio, forza_euristico)
                    if not subset:
                        continue

                    composizioni_disponibili.remove(composizione)
                    assegnazioni.append(
                        AssegnazioneViaggio(
                            composizione_id=composizione.id_composizione,
                            ordini_ids=[ordine.id for ordine in subset],
                        )
                    )
                    subset_ids = {ordine.id for ordine in subset}
                    ordini_assegnati_ids.update(subset_ids)
                    ordini_restanti_cluster = [
                        ordine for ordine in ordini_restanti_cluster if ordine.id not in subset_ids
                    ]

                if len(cluster) == 1 and ordini_restanti_cluster:
                    ordini_isolati_non_serviti.extend(ordini_restanti_cluster)

            # Ordini isolati (cluster di un solo elemento, tipico dei punti di
            # rumore DBSCAN) rimasti scoperti: ultimo tentativo di aggiungerli
            # a un viaggio gia' pianificato in questa esecuzione prima di
            # dichiararli non assegnabili.
            for ordine in ordini_isolati_non_serviti:
                for assegnazione in assegnazioni:
                    composizione = composizioni_by_id[assegnazione.composizione_id]
                    camion = composizione.camion
                    dipendenti = [composizione.dipendente_1, composizione.dipendente_2]
                    if not self._ordine_idoneo(ordine, camion, dipendenti):
                        continue

                    ordini_viaggio = [
                        ordini_by_id[ordine_id] for ordine_id in assegnazione.ordini_ids
                    ]
                    peso_usato = sum(o.peso for o in ordini_viaggio)
                    volume_usato = sum(o.volume_cargo for o in ordini_viaggio)
                    if peso_usato + ordine.peso > camion.peso_massimo:
                        continue
                    if volume_usato + ordine.volume_cargo > camion.volume_massimo:
                        continue

                    forza_euristico = (
                        time.perf_counter() - inizio_esecuzione
                    ) > budget_esecuzione_secondi
                    nuovo_subset = ordini_viaggio + [ordine]
                    usa_esatto = not forza_euristico and len(nuovo_subset) <= SOGLIA_NODI_HELD_KARP
                    if stima_durata_viaggio(nuovo_subset, usa_esatto) > durata_viaggio:
                        continue

                    assegnazione.ordini_ids.append(ordine.id)
                    ordini_assegnati_ids.add(ordine.id)
                    break

            ordini_non_assegnati = [
                ordine.id for ordine in tutti_candidati if ordine.id not in ordini_assegnati_ids
            ]

            return PianoGiornaliero(assegnazioni=assegnazioni, ordini_non_assegnati=ordini_non_assegnati)

    def _knapsack_capacita_massima(
        self, ordini: list[Ordine], camion: Camion, time_limit: float
    ) -> list[Ordine] | None:
        """Sottoinsieme che massimizza il numero di ordini caricabili rispettando peso/volume.

        Restituisce None se il solver non raggiunge lo stato "Optimal" (va
        segnalato al chiamante invece di essere confuso con un sottoinsieme
        vuoto valido).
        """
        problema = pulp.LpProblem("calcola_piano_cluster", pulp.LpMaximize)
        x = {ordine.id: pulp.LpVariable(f"x_{ordine.id}", cat="Binary") for ordine in ordini}

        problema += pulp.lpSum(x.values())
        problema += pulp.lpSum(ordine.peso * x[ordine.id] for ordine in ordini) <= camion.peso_massimo
        problema += (
            pulp.lpSum(ordine.volume_cargo * x[ordine.id] for ordine in ordini) <= camion.volume_massimo
        )

        problema.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))

        if pulp.LpStatus[problema.status] != "Optimal":
            return None
        return [ordine for ordine in ordini if x[ordine.id].value() == 1]

    def _applica_vincolo_durata(
        self, subset: list[Ordine], durata_viaggio: timedelta, forza_euristico: bool
    ) -> list[Ordine]:
        """Riduce il sottoinsieme finche' la durata stimata rientra nel budget.

        Ad ogni iterazione rimuove l'ordine che contribuisce di piu' alla
        lunghezza del tour attuale (non rifa' il knapsack: la selezione di
        capacita' resta quella del passo precedente, si scarta solo il punto
        piu' dispersivo).
        """
        subset = list(subset)
        while subset:
            usa_esatto = not forza_euristico and len(subset) <= SOGLIA_NODI_HELD_KARP
            if stima_durata_viaggio(subset, usa_esatto) <= durata_viaggio:
                return subset
            subset = self._rimuovi_ordine_piu_dispersivo(subset, usa_esatto)
        return subset

    def _rimuovi_ordine_piu_dispersivo(self, subset: list[Ordine], usa_esatto: bool) -> list[Ordine]:
        calcola_tour = tour_esatto if usa_esatto else tour_euristico
        _, distanza_base = calcola_tour(subset)
        peggiore = max(
            subset,
            key=lambda o: distanza_base
            - calcola_tour([altro for altro in subset if altro.id != o.id])[1],
        )
        return [o for o in subset if o.id != peggiore.id]

    def applica_piano(
        self,
        piano: PianoGiornaliero,
        ora_partenza: datetime,
        durata_viaggio: timedelta = timedelta(hours=8),
    ) -> RisultatoPianificazione:
        viaggi_creati: list[str] = []
        ordini_assegnati = 0

        with self.session_factory() as session:
            prefisso = f"V-{ora_partenza:%Y%m%d}-"
            progressivo = len(
                session.scalars(select(Viaggio.id).where(Viaggio.id.like(f"{prefisso}%"))).all()
            )

            for assegnazione in piano.assegnazioni:
                progressivo += 1
                viaggio_id = f"{prefisso}{progressivo:02d}"

                session.add(
                    Viaggio(
                        id=viaggio_id,
                        data_partenza_prevista=ora_partenza,
                        data_arrivo_prevista=ora_partenza + durata_viaggio,
                        km_percorsi=None,
                        stato_viaggio=StatoViaggio.PIANIFICATO,
                        composizione_id=assegnazione.composizione_id,
                    )
                )

                ordini = session.scalars(
                    select(Ordine).where(Ordine.id.in_(assegnazione.ordini_ids))
                ).all()
                for ordine in ordini:
                    ordine.viaggio_id = viaggio_id
                    ordine.stato_ordine = StatoOrdine.PIANIFICATO

                viaggi_creati.append(viaggio_id)
                ordini_assegnati += len(assegnazione.ordini_ids)

            session.commit()

        return RisultatoPianificazione(viaggi_creati=viaggi_creati, ordini_assegnati=ordini_assegnati)
