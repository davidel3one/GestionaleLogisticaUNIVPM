import csv
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook
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


def _righe_da_xlsx(percorso_file: Path) -> tuple[list[str] | None, list[dict[str, str | None]]]:
    """Legge un file Excel (RF9) e lo riporta alla stessa forma di csv.DictReader (header +
    righe come dict di stringhe), cosi' la validazione in importa_ordini resta unica per
    entrambi i formati. Le celle mancanti in coda a una riga corta diventano None, come il
    restval di DictReader per una riga CSV con meno colonne dell'header."""
    wb = load_workbook(percorso_file, read_only=True, data_only=True)
    try:
        righe_grezze = list(wb.active.iter_rows(values_only=True))
    finally:
        wb.close()
    if not righe_grezze:
        return None, []

    header = [str(valore) if valore is not None else "" for valore in righe_grezze[0]]
    righe = []
    for row in righe_grezze[1:]:
        valori = list(row) + [None] * (len(header) - len(row))
        righe.append({col: None if v is None else str(v) for col, v in zip(header, valori)})
    return header, righe


@dataclass
class ErroreImport:
    riga: int
    messaggio: str
    id_ordine: str | None = None
    cliente: str | None = None


@dataclass
class RisultatoImport:
    ordini_creati: int = 0
    errori: list[ErroreImport] = field(default_factory=list)


@dataclass
class AnteprimaImport:
    """Esito di una validazione a secco (RF9, GUI): nessuna riga viene persistita."""

    righe_valide: int = 0
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
    """Idoneita' categoria<->risorsa (RF11): sponda idraulica per Big, certificazione gas per
    CertificazioneGas. Include anche RF3/RF6: un camion dismesso o un dipendente licenziato
    (flg_attivo=False, soft delete) non sono mai idonei per un nuovo viaggio qualunque sia la
    categoria dell'ordine - i viaggi gia' pianificati/in corso non vengono toccati retroattivamente."""
    if not camion.flg_attivo or not all(dipendente.flg_attivo for dipendente in dipendenti):
        return False
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
    if not camion.flg_attivo:
        return EsitoValidazioneOrdine(ammesso=False, motivo="Il camion non e' piu' in servizio")
    if not all(dipendente.flg_attivo for dipendente in dipendenti):
        return EsitoValidazioneOrdine(
            ammesso=False, motivo="Un membro della squadra non e' piu' in servizio (licenziato)"
        )
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
) -> tuple[str, int]:
    """Genera il prossimo id sequenziale V-YYYYMMDD-NN per il giorno e persiste il Viaggio
    (piu' l'aggancio degli ordini indicati, se presenti) sulla session gia' aperta passata come
    parametro. Non apre una sessione propria e non fa commit: il chiamante controlla i confini
    della transazione (necessario per preservare l'atomicita' di un batch multi-viaggio in
    MotoreOttimizzazione.applica_piano).

    Aggancia solo gli ordini ancora disponibili (stato RICEVUTO e viaggio_id None): tra il calcolo
    di un piano e la sua applicazione un ordine candidato puo' essere stato agganciato altrove (es.
    a una bozza manuale RF10), e riassegnarlo qui lo ruberebbe silenziosamente. Restituisce l'id del
    viaggio e il numero di ordini effettivamente agganciati.
    """
    prefisso = f"V-{ora_partenza:%Y%m%d}-"
    progressivo = len(session.scalars(select(Viaggio.id).where(Viaggio.id.like(f"{prefisso}%"))).all()) + 1
    viaggio_id = f"{prefisso}{progressivo:02d}"

    session.add(
        Viaggio(
            id=viaggio_id,
            data_partenza_prevista=ora_partenza,
            data_arrivo_prevista=data_arrivo_prevista,
            data_creazione=datetime.now(),
            km_percorsi=None,
            stato_viaggio=stato_viaggio,
            composizione_id=composizione_id,
        )
    )
    ordini_agganciati = 0
    if ordini_ids:
        ordini_da_agganciare = session.scalars(
            select(Ordine).where(
                Ordine.id.in_(ordini_ids),
                Ordine.stato_ordine == StatoOrdine.RICEVUTO,
                Ordine.viaggio_id.is_(None),
            )
        ).all()
        for o in ordini_da_agganciare:
            o.viaggio_id = viaggio_id
            o.stato_ordine = StatoOrdine.PIANIFICATO
        ordini_agganciati = len(ordini_da_agganciare)
    session.flush()
    return viaggio_id, ordini_agganciati


def _prepara_ordini_da_file(
    percorso_file: Path, negozio_partner: str, id_esistenti: set[str]
) -> tuple[list[Ordine], list[ErroreImport]]:
    """Legge e valida le righe del file (RF9) senza persistere nulla: le righe valide diventano
    `Ordine` pronti per una sessione, le righe scartate finiscono in `ErroreImport` (con
    `id_ordine`/`cliente` quando disponibili, per la tabella di anteprima lato GUI). Riusata sia
    dall'anteprima a secco sia dal commit reale, cosi' la validazione esiste in un solo posto -
    non muta `id_esistenti` del chiamante (lavora su una copia)."""
    if not negozio_partner.strip():
        return [], [ErroreImport(riga=0, messaggio="Negozio partner obbligatorio")]

    if percorso_file.suffix.lower() == ".xlsx":
        header, righe = _righe_da_xlsx(percorso_file)
    else:
        with open(percorso_file, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            header = reader.fieldnames
            righe = list(reader)

    if header != COLONNE_ATTESE:
        return [], [
            ErroreImport(
                riga=0,
                messaggio=f"Header non riconosciuto, attese colonne: {';'.join(COLONNE_ATTESE)}",
            )
        ]

    negozio_partner = negozio_partner.strip()
    id_esistenti = set(id_esistenti)
    ordini_validi: list[Ordine] = []
    errori: list[ErroreImport] = []

    for numero_riga, riga in enumerate(righe, start=2):
        id_ordine = riga["ID_Ordine"]
        cliente = riga.get("Cliente")
        if id_ordine in id_esistenti:
            errori.append(ErroreImport(numero_riga, "ID duplicato", id_ordine, cliente))
            continue

        # TypeError: riga con meno colonne dell'header -> csv.DictReader riempie i campi
        # mancanti con None (float(None)/Enum(None) sollevano TypeError). Un try/except per
        # campo (non uno unico) per dare un motivo di scarto specifico (RF9, tabella di
        # anteprima lato GUI) invece di un messaggio tecnico generico.
        try:
            peso = float(riga["Peso"])
        except (ValueError, TypeError):
            errori.append(ErroreImport(numero_riga, "Peso non valido", id_ordine, cliente))
            continue
        try:
            volume = float(riga["Volume"])
        except (ValueError, TypeError):
            errori.append(ErroreImport(numero_riga, "Volume non valido", id_ordine, cliente))
            continue
        try:
            categoria = CategoriaConsegna(riga["Categoria"])
        except (ValueError, TypeError):
            errori.append(ErroreImport(numero_riga, "Categoria non valida", id_ordine, cliente))
            continue

        parti = [parte.strip() for parte in riga["Indirizzo"].rsplit(",", 1)]
        if len(parti) != 2:
            errori.append(ErroreImport(numero_riga, "Indirizzo non valido", id_ordine, cliente))
            continue
        indirizzo, comune = parti
        if riga["Provincia"] is None:
            # Riga con meno colonne dell'header in cui manca solo l'ultima
            # (Provincia): Peso/Volume/Categoria sono presenti e superano il
            # parsing sopra, quindi il TypeError non scatta e riga["Provincia"]
            # resta None (restval di csv.DictReader). Va scartata, non deve
            # far crashare l'import con AttributeError su None.strip().
            errori.append(ErroreImport(numero_riga, "Provincia mancante", id_ordine, cliente))
            continue
        provincia = riga["Provincia"].strip()
        coordinate = geocodifica_comune(comune, provincia)
        lat, lon = coordinate if coordinate is not None else (None, None)

        ordini_validi.append(
            Ordine(
                id=id_ordine,
                indirizzo=indirizzo,
                comune=comune,
                provincia=provincia,
                lat=lat,
                lon=lon,
                cliente=cliente,
                peso=peso,
                volume_cargo=volume,
                categoria_consegna=categoria,
                stato_ordine=StatoOrdine.RICEVUTO,
                data_importazione=datetime.now(),
                data_consegna=None,
                viaggio_id=None,
                negozio_partner=negozio_partner,
            )
        )
        id_esistenti.add(id_ordine)

    return ordini_validi, errori


class GestoreLogistica:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def importa_ordini(self, percorso_file: Path, negozio_partner: str) -> RisultatoImport:
        with self.session_factory() as session:
            id_esistenti = set(session.scalars(select(Ordine.id)))
            nuovi_ordini, errori = _prepara_ordini_da_file(percorso_file, negozio_partner, id_esistenti)
            session.add_all(nuovi_ordini)
            session.commit()
            return RisultatoImport(ordini_creati=len(nuovi_ordini), errori=errori)

    def anteprima_import_ordini(self, percorso_file: Path, negozio_partner: str) -> AnteprimaImport:
        """RF9 (anteprima, GUI): valida il file come farebbe `importa_ordini`, ma senza
        scrivere nulla sul DB - usata dallo step "Risultato" del modale Importa CSV prima che
        l'utente confermi con "Importa N ordini"."""
        with self.session_factory() as session:
            id_esistenti = set(session.scalars(select(Ordine.id)))
        nuovi_ordini, errori = _prepara_ordini_da_file(percorso_file, negozio_partner, id_esistenti)
        return AnteprimaImport(righe_valide=len(nuovi_ordini), errori=errori)

    def elenco_negozi_partner(self) -> list[str]:
        """Valori distinti di `negozio_partner` gia' visti (RF9, GUI): suggerimenti per il
        selettore "select o crea nuovo" del modale Importa CSV - non e' un'entita' a se' nel
        modello dati, solo una stringa libera su `Ordine`."""
        with self.session_factory() as session:
            valori = session.scalars(
                select(Ordine.negozio_partner).distinct().where(Ordine.negozio_partner.is_not(None))
            ).all()
            return sorted(v for v in valori if v)

    def importa_ordini_async(self, percorso_file: Path, negozio_partner: str) -> "Future[RisultatoImport]":
        """RNF3: come importa_ordini, ma eseguito su un thread separato per non bloccare la GUI
        durante l'importazione massiva (RF9)."""
        return esegui_in_background(lambda: self.importa_ordini(percorso_file, negozio_partner))

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

            viaggio_id, _ = crea_viaggio_persistito(
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

    def verifica_partenze(self, ora_riferimento: datetime | None = None) -> list[str]:
        """RF14: al superamento dell'orario di partenza programmato, porta i viaggi Pianificato
        a InCorso (inibendo cosi' ulteriori modifiche al carico, gia' possibili solo su viaggi
        IN_COMPOSIZIONE) e i relativi Ordini da Pianificato a InConsegna. Pensato per essere
        invocato periodicamente dallo scheduler interno
        (config.ini [scheduler].verifica_partenza_intervallo_minuti). Ritorna gli id dei viaggi avviati.
        """
        ora_riferimento = ora_riferimento or datetime.now()
        with self.session_factory() as session:
            viaggi_da_avviare = session.scalars(
                select(Viaggio).where(
                    Viaggio.stato_viaggio == StatoViaggio.PIANIFICATO,
                    Viaggio.data_partenza_prevista <= ora_riferimento,
                )
            ).all()
            for viaggio in viaggi_da_avviare:
                for ordine in viaggio.ordini:
                    ordine.stato_ordine = StatoOrdine.IN_CONSEGNA
                viaggio.stato_viaggio = StatoViaggio.IN_CORSO
            session.commit()
            return [viaggio.id for viaggio in viaggi_da_avviare]
