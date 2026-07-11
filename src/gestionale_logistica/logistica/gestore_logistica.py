import csv
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from gestionale_logistica.concorrenza import esegui_in_background
from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Ordine, Viaggio
from gestionale_logistica.logistica.geocoding import geocodifica_comune

COLONNE_ATTESE = ["ID_Ordine", "Cliente", "Indirizzo", "Categoria", "Peso", "Volume", "Provincia"]

ordine = CRUDBase[Ordine](Ordine)
viaggio = CRUDBase[Viaggio](Viaggio)


@dataclass
class ErroreImport:
    riga: int
    messaggio: str


@dataclass
class RisultatoImport:
    ordini_creati: int = 0
    errori: list[ErroreImport] = field(default_factory=list)


@dataclass
class EsitoValidazioneOrdine:
    ammesso: bool
    motivo: str | None = None


@dataclass
class RisultatoOperazioneViaggio:
    ok: bool
    viaggio_id: str | None = None
    motivo: str | None = None


def verifica_idoneita_risorsa(ordine: Ordine, camion: Camion, dipendenti: list[Dipendente]) -> bool:
    """Idoneita' categoria<->risorsa (RF11): sponda idraulica per Big, certificazione gas per CertificazioneGas."""
    if ordine.categoria_consegna == CategoriaConsegna.BIG:
        return camion.flg_sponda_idraulica
    if ordine.categoria_consegna == CategoriaConsegna.CERTIFICAZIONE_GAS:
        return any(dipendente.flg_certificazione_gas for dipendente in dipendenti)
    return True


def valida_ordine_per_viaggio(
    ordine: Ordine,
    camion: Camion,
    dipendenti: list[Dipendente],
    peso_occupato: float,
    volume_occupato: float,
) -> EsitoValidazioneOrdine:
    """Validazione RF11 completa (idoneita' + capacita' residua) con motivo del rifiuto."""
    if not verifica_idoneita_risorsa(ordine, camion, dipendenti):
        if ordine.categoria_consegna == CategoriaConsegna.BIG:
            return EsitoValidazioneOrdine(
                ammesso=False,
                motivo="Il camion non ha la sponda idraulica necessaria per ordini di categoria Big",
            )
        return EsitoValidazioneOrdine(
            ammesso=False,
            motivo="Nessun membro della squadra ha la certificazione gas necessaria",
        )
    if peso_occupato + ordine.peso > camion.peso_massimo:
        return EsitoValidazioneOrdine(
            ammesso=False, motivo="Il peso dell'ordine supererebbe la capacita' massima del camion"
        )
    if volume_occupato + ordine.volume_cargo > camion.volume_massimo:
        return EsitoValidazioneOrdine(
            ammesso=False, motivo="Il volume dell'ordine supererebbe la capacita' massima del camion"
        )
    return EsitoValidazioneOrdine(ammesso=True)


def crea_viaggio_persistito(
    session: Session,
    ora_partenza: datetime,
    data_arrivo_prevista: datetime,
    composizione_id: str,
    stato_viaggio: StatoViaggio,
    ordini_ids: tuple[str, ...] = (),
) -> str:
    """Genera il prossimo id sequenziale V-YYYYMMDD-NN per il giorno e persiste il Viaggio
    (piu' l'aggancio degli ordini indicati, se presenti) sulla session gia' aperta passata come
    parametro. Non apre una sessione propria e non fa commit: il chiamante controlla i confini
    della transazione (necessario per preservare l'atomicita' di un batch multi-viaggio in
    MotoreOttimizzazione.applica_piano).
    """
    prefisso = f"V-{ora_partenza:%Y%m%d}-"
    progressivo = len(session.scalars(select(Viaggio.id).where(Viaggio.id.like(f"{prefisso}%"))).all()) + 1
    viaggio_id = f"{prefisso}{progressivo:02d}"

    session.add(
        Viaggio(
            id=viaggio_id,
            data_partenza_prevista=ora_partenza,
            data_arrivo_prevista=data_arrivo_prevista,
            km_percorsi=None,
            stato_viaggio=stato_viaggio,
            composizione_id=composizione_id,
        )
    )
    if ordini_ids:
        ordini_da_agganciare = session.scalars(select(Ordine).where(Ordine.id.in_(ordini_ids))).all()
        for o in ordini_da_agganciare:
            o.viaggio_id = viaggio_id
            o.stato_ordine = StatoOrdine.PIANIFICATO
    session.flush()
    return viaggio_id


class GestoreLogistica:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def importa_ordini(self, percorso_file: Path) -> RisultatoImport:
        with open(percorso_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            if reader.fieldnames != COLONNE_ATTESE:
                return RisultatoImport(
                    errori=[
                        ErroreImport(
                            riga=0,
                            messaggio=f"Header non riconosciuto, attese colonne: {';'.join(COLONNE_ATTESE)}",
                        )
                    ]
                )

            risultato = RisultatoImport()
            with self.session_factory() as session:
                id_esistenti = set(session.scalars(select(Ordine.id)))
                nuovi_ordini = []

                for numero_riga, riga in enumerate(reader, start=2):
                    id_ordine = riga["ID_Ordine"]
                    if id_ordine in id_esistenti:
                        risultato.errori.append(
                            ErroreImport(numero_riga, f"ID_Ordine '{id_ordine}' gia' presente")
                        )
                        continue

                    try:
                        peso = float(riga["Peso"])
                        volume = float(riga["Volume"])
                        categoria = CategoriaConsegna(riga["Categoria"])
                    except ValueError as errore:
                        risultato.errori.append(ErroreImport(numero_riga, str(errore)))
                        continue

                    parti = [parte.strip() for parte in riga["Indirizzo"].rsplit(",", 1)]
                    if len(parti) != 2:
                        risultato.errori.append(
                            ErroreImport(numero_riga, f"Indirizzo senza comune: '{riga['Indirizzo']}'")
                        )
                        continue
                    indirizzo, comune = parti
                    provincia = riga["Provincia"].strip()
                    coordinate = geocodifica_comune(comune, provincia)
                    lat, lon = coordinate if coordinate is not None else (None, None)

                    nuovi_ordini.append(
                        Ordine(
                            id=id_ordine,
                            indirizzo=indirizzo,
                            comune=comune,
                            provincia=provincia,
                            lat=lat,
                            lon=lon,
                            cliente=riga["Cliente"],
                            peso=peso,
                            volume_cargo=volume,
                            categoria_consegna=categoria,
                            stato_ordine=StatoOrdine.RICEVUTO,
                            data_consegna=None,
                            viaggio_id=None,
                        )
                    )
                    id_esistenti.add(id_ordine)

                session.add_all(nuovi_ordini)
                session.commit()
                risultato.ordini_creati = len(nuovi_ordini)

            return risultato

    def importa_ordini_async(self, percorso_file: Path) -> "Future[RisultatoImport]":
        """RNF3: come importa_ordini, ma eseguito su un thread separato per non bloccare la GUI
        durante l'importazione massiva (RF9)."""
        return esegui_in_background(lambda: self.importa_ordini(percorso_file))

    def avvia_composizione_viaggio(
        self,
        composizione_id: str,
        ora_partenza: datetime,
        durata_prevista: timedelta = timedelta(hours=8),
    ) -> RisultatoOperazioneViaggio:
        """RF10 (avvio): crea un Viaggio in stato IN_COMPOSIZIONE, senza ordini, per una
        ComposizioneSquadra idonea/attiva/libera in quella data. `data_partenza_prevista` e'
        impostata subito (non alla chiusura): e' il campo su cui calcola_piano verifica se una
        composizione e' gia' occupata quel giorno, quindi una bozza senza questo campo sarebbe
        invisibile a quel controllo.
        """
        with self.session_factory() as session:
            composizione = session.get(ComposizioneSquadra, composizione_id)
            if composizione is None:
                return RisultatoOperazioneViaggio(
                    ok=False, motivo=f"Composizione '{composizione_id}' non trovata"
                )
            if not composizione.flg_attiva:
                return RisultatoOperazioneViaggio(ok=False, motivo="Composizione non attiva")

            giorno = ora_partenza.date()
            fuori_validita = composizione.data_inizio_validita.date() > giorno or (
                composizione.data_fine_validita is not None
                and composizione.data_fine_validita.date() < giorno
            )
            if fuori_validita:
                return RisultatoOperazioneViaggio(
                    ok=False, motivo="Composizione non valida in questa data"
                )

            inizio_giorno = datetime(giorno.year, giorno.month, giorno.day)
            fine_giorno = inizio_giorno + timedelta(days=1)
            occupata = session.scalar(
                select(Viaggio.id).where(
                    Viaggio.composizione_id == composizione_id,
                    Viaggio.data_partenza_prevista >= inizio_giorno,
                    Viaggio.data_partenza_prevista < fine_giorno,
                )
            )
            if occupata is not None:
                return RisultatoOperazioneViaggio(
                    ok=False, motivo="Composizione gia' occupata in questa data"
                )

            viaggio_id = crea_viaggio_persistito(
                session,
                ora_partenza=ora_partenza,
                data_arrivo_prevista=ora_partenza + durata_prevista,
                composizione_id=composizione_id,
                stato_viaggio=StatoViaggio.IN_COMPOSIZIONE,
            )
            session.commit()
            return RisultatoOperazioneViaggio(ok=True, viaggio_id=viaggio_id)

    def aggiungi_ordine_a_viaggio(self, viaggio_id: str, ordine_id: str) -> EsitoValidazioneOrdine:
        """RF10/RF11 (aggiunta): valida l'ordine candidato contro lo stato attuale del viaggio
        in composizione; se ammesso lo aggancia (viaggio_id + stato_ordine=PIANIFICATO) e
        aggiorna i totali, altrimenti il viaggio resta invariato e viene restituito il motivo.
        """
        with self.session_factory() as session:
            viaggio = session.get(Viaggio, viaggio_id)
            if viaggio is None:
                return EsitoValidazioneOrdine(ammesso=False, motivo=f"Viaggio '{viaggio_id}' non trovato")
            if viaggio.stato_viaggio != StatoViaggio.IN_COMPOSIZIONE:
                return EsitoValidazioneOrdine(
                    ammesso=False, motivo="Il viaggio non e' in fase di composizione"
                )

            ordine_candidato = session.get(Ordine, ordine_id)
            if ordine_candidato is None:
                return EsitoValidazioneOrdine(ammesso=False, motivo=f"Ordine '{ordine_id}' non trovato")
            if ordine_candidato.viaggio_id is not None:
                return EsitoValidazioneOrdine(ammesso=False, motivo="Ordine gia' assegnato a un viaggio")

            composizione = viaggio.composizione
            camion = composizione.camion
            dipendenti = [composizione.dipendente_1, composizione.dipendente_2]
            peso_occupato = sum(o.peso for o in viaggio.ordini)
            volume_occupato = sum(o.volume_cargo for o in viaggio.ordini)

            esito = valida_ordine_per_viaggio(
                ordine_candidato, camion, dipendenti, peso_occupato, volume_occupato
            )
            if not esito.ammesso:
                return esito

            ordine_candidato.viaggio_id = viaggio_id
            ordine_candidato.stato_ordine = StatoOrdine.PIANIFICATO
            session.commit()
            return esito

    def chiudi_composizione_viaggio(self, viaggio_id: str) -> RisultatoOperazioneViaggio:
        """RF10 (chiusura): porta il viaggio da IN_COMPOSIZIONE a PIANIFICATO definitivo.
        Richiede almeno un ordine agganciato: un viaggio vuoto non viene salvato come pianificato.
        """
        with self.session_factory() as session:
            viaggio = session.get(Viaggio, viaggio_id)
            if viaggio is None:
                return RisultatoOperazioneViaggio(ok=False, motivo=f"Viaggio '{viaggio_id}' non trovato")
            if viaggio.stato_viaggio != StatoViaggio.IN_COMPOSIZIONE:
                return RisultatoOperazioneViaggio(
                    ok=False, motivo="Il viaggio non e' in fase di composizione"
                )
            if not viaggio.ordini:
                return RisultatoOperazioneViaggio(
                    ok=False, motivo="Impossibile chiudere un viaggio senza ordini"
                )

            viaggio.stato_viaggio = StatoViaggio.PIANIFICATO
            session.commit()
            return RisultatoOperazioneViaggio(ok=True, viaggio_id=viaggio_id)
