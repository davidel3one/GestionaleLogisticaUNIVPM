import shutil
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import CategoriaConsegna, StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Allegato,
    CausaleFallimento,
    EsitoConsegna,
    Ordine,
    RegistroEsiti,
    ReportConsuntivo,
    Viaggio,
)
from gestionale_logistica.logistica.gestore_logistica import FILTRO_TUTTI, _normalizza_filtro_multiplo

esito_consegna = CRUDBase[EsitoConsegna](EsitoConsegna)
causale_fallimento = CRUDBase[CausaleFallimento](CausaleFallimento)
registro_esiti = CRUDBase[RegistroEsiti](RegistroEsiti)
allegato = CRUDBase[Allegato](Allegato)
report_consuntivo = CRUDBase[ReportConsuntivo](ReportConsuntivo)

CARTELLA_REPORT_DEFAULT = Path("report")
CARTELLA_ALLEGATI_DEFAULT = Path("allegati")


@dataclass
class RisultatoGenerazioneReport:
    generato: bool
    report_id: int | None = None
    percorso_file: str | None = None
    motivo: str | None = None


@dataclass
class RisultatoRegistrazioneEsito:
    ok: bool
    esito_id: int | None = None
    motivo: str | None = None


@dataclass
class RisultatoOperazione:
    ok: bool
    motivo: str | None = None


@dataclass
class OrdineInTransitoVista:
    id: str
    cliente: str
    indirizzo: str
    comune: str
    categoria_consegna: CategoriaConsegna
    stato_ordine: StatoOrdine


@dataclass
class ViaggioInTransito:
    id: str
    data_partenza_prevista: datetime
    ordini: list[OrdineInTransitoVista] = field(default_factory=list)


@dataclass
class EsitoVista:
    """Riga della tab "Esiti" (storico): un EsitoConsegna gia' registrato. Un ordine puo'
    comparire piu' volte se e' fallito ed e' stato ripianificato (RF17, un nuovo esito per il
    viaggio successivo) - non e' una vista 1:1 su Ordine, e' 1:1 su EsitoConsegna."""

    id: int
    ordine_id: str
    cliente: str
    indirizzo: str
    peso: float
    volume_cargo: float
    esito: str
    causale_codice: str | None
    causale: str | None
    data_registrazione: datetime


@dataclass
class PaginaEsiti:
    esiti: list[EsitoVista]
    totale: int


@dataclass
class AllegatoVista:
    id: int
    nome_file: str
    percorso_file: str
    tipo_file: str
    data_caricamento: datetime


class GestoreRendicontazione:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        cartella_output: Path = CARTELLA_REPORT_DEFAULT,
        cartella_allegati: Path = CARTELLA_ALLEGATI_DEFAULT,
    ) -> None:
        self.session_factory = session_factory
        self.cartella_output = cartella_output
        self.cartella_allegati = cartella_allegati

    def genera_report_giornaliero(self, giorno: datetime | None = None) -> RisultatoGenerazioneReport:
        """RF19: alle 21:00 (config.ini [scheduler].report_orario) aggrega gli esiti degli ordini
        dei viaggi partiti quel giorno per negozio partner e genera il report consuntivo in PDF.
        Il raggruppamento per giorno usa Viaggio.data_partenza_prevista, non Ordine.data_consegna,
        per coerenza con lo stesso pattern gia' usato da calcola_piano (RF13) — vedi divergenze-ea.md.
        "Invio" del report (RF19) e' fuori scope: non esiste un contatto email per negozio partner
        nel modello dati, solo generazione e persistenza locale del file.
        """
        giorno = giorno or datetime.now()
        data_riferimento = datetime(giorno.year, giorno.month, giorno.day)

        with self.session_factory() as session:
            # Fonte del report: gli EsitoConsegna registrati (RF16) nel RegistroEsiti del giorno,
            # non lo stato_ordine transitorio. Un ordine Fallito (RF17) viene riportato a RICEVUTO
            # e sganciato dal viaggio, quindi il suo fallimento sopravvive solo nell'esito
            # persistente; leggere lo stato dell'ordine perderebbe ogni consegna fallita.
            registro_esistente = session.scalar(
                select(RegistroEsiti)
                .where(RegistroEsiti.data_riferimento == data_riferimento)
                .options(selectinload(RegistroEsiti.esiti).selectinload(EsitoConsegna.ordine))
            )
            if registro_esistente is None or not registro_esistente.esiti:
                return RisultatoGenerazioneReport(
                    generato=False, motivo="Nessuna consegna da rendicontare per questa data"
                )

            report_esistente = session.scalar(
                select(ReportConsuntivo).where(ReportConsuntivo.registro_id == registro_esistente.id)
            )

            esiti = registro_esistente.esiti
            conteggio_per_negozio: dict[str, dict[str, int]] = defaultdict(
                lambda: {"completati": 0, "falliti": 0}
            )
            for e in esiti:
                negozio = e.ordine.negozio_partner or "Non specificato"
                chiave = "completati" if e.stato_esito == StatoEsito.COMPLETATO else "falliti"
                conteggio_per_negozio[negozio][chiave] += 1

            ordini_consegnati = sum(v["completati"] for v in conteggio_per_negozio.values())
            ordini_falliti = sum(v["falliti"] for v in conteggio_per_negozio.values())
            negozi_partner = ", ".join(sorted(conteggio_per_negozio))
            # Ordini distinti coinvolti: un ordine ripianificato lo stesso giorno puo' avere piu'
            # esiti (un Fallito + un Completato), ma nella relazione M2M compare una volta sola.
            ordini_coinvolti = list({e.ordine_id: e.ordine for e in esiti}.values())

            self.cartella_output.mkdir(parents=True, exist_ok=True)
            percorso_file = self.cartella_output / f"report_{data_riferimento:%Y%m%d}.pdf"
            _genera_pdf(
                percorso_file, data_riferimento, conteggio_per_negozio, ordini_consegnati, ordini_falliti
            )

            if report_esistente is not None:
                # Il job schedulato (RF19) puo' rigenerare piu' volte lo stesso giorno: un ordine
                # ancora IN_CONSEGNA alla prima generazione (es. alle 21:00) puo' completarsi o
                # fallire dopo. Aggiorniamo la riga esistente invece di rifiutare, cosi' il report
                # riflette sempre lo stato corrente ed e' idempotente rispetto a chiamate ripetute -
                # niente riga duplicata, l'invariante "un ReportConsuntivo per registro" e' preservata.
                report_esistente.data_generazione = datetime.now()
                report_esistente.ordini_consegnati = ordini_consegnati
                report_esistente.ordini_falliti = ordini_falliti
                report_esistente.negozi_partner = negozi_partner
                report_esistente.percorso_file = str(percorso_file)
                report_esistente.ordini = ordini_coinvolti
                session.commit()
                return RisultatoGenerazioneReport(
                    generato=True, report_id=report_esistente.id, percorso_file=str(percorso_file)
                )

            report = ReportConsuntivo(
                data_generazione=datetime.now(),
                ordini_consegnati=ordini_consegnati,
                ordini_falliti=ordini_falliti,
                formato_output="PDF",
                negozi_partner=negozi_partner,
                percorso_file=str(percorso_file),
                registro_id=registro_esistente.id,
            )
            report.ordini = ordini_coinvolti
            session.add(report)
            session.commit()

            return RisultatoGenerazioneReport(
                generato=True, report_id=report.id, percorso_file=str(percorso_file)
            )

    def registra_esito(
        self,
        ordine_id: str,
        stato_esito: StatoEsito,
        causale_codice: str | None = None,
    ) -> RisultatoRegistrazioneEsito:
        """RF16: registra l'esito di consegna di un ordine in transito. RF17 (automatico, non
        un passo separato): se l'esito e' Fallito, l'ordine torna RICEVUTO e sganciato dal
        viaggio (viaggio_id=None), il che lo rimette tra i candidati di
        MotoreOttimizzazione.suggerisci_ordini/calcola_piano.
        """
        with self.session_factory() as session:
            ordine = session.get(Ordine, ordine_id)
            if ordine is None:
                return RisultatoRegistrazioneEsito(ok=False, motivo=f"Ordine '{ordine_id}' non trovato")
            if ordine.viaggio is None or ordine.viaggio.stato_viaggio != StatoViaggio.IN_CORSO:
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo="L'ordine non e' su un viaggio in corso"
                )
            # Idempotenza ancorata al viaggio corrente, non all'ordine: dopo un Fallito (RF17)
            # l'ordine torna in coda e puo' ricevere un nuovo esito su un viaggio successivo.
            # Un secondo esito e' rifiutato solo se ne esiste gia' uno per QUESTO stesso viaggio.
            viaggio_id = ordine.viaggio_id
            esito_esistente = session.scalar(
                select(EsitoConsegna).where(
                    EsitoConsegna.ordine_id == ordine_id,
                    EsitoConsegna.viaggio_id == viaggio_id,
                )
            )
            if esito_esistente is not None:
                return RisultatoRegistrazioneEsito(ok=False, motivo="Ordine gia' associato a un esito")

            if stato_esito == StatoEsito.FALLITO:
                if causale_codice is None:
                    return RisultatoRegistrazioneEsito(
                        ok=False, motivo="Causale obbligatoria per un esito Fallito"
                    )
                if session.get(CausaleFallimento, causale_codice) is None:
                    return RisultatoRegistrazioneEsito(
                        ok=False, motivo=f"Causale '{causale_codice}' non trovata"
                    )

            # Raggruppamento per giorno di PARTENZA del viaggio (non per oggi): stesso criterio
            # usato da calcola_piano (RF13), per non creare un RegistroEsiti disallineato quando
            # l'esito viene registrato un giorno dopo la partenza.
            partenza = ordine.viaggio.data_partenza_prevista
            data_riferimento = datetime(partenza.year, partenza.month, partenza.day)
            registro = session.scalar(
                select(RegistroEsiti).where(RegistroEsiti.data_riferimento == data_riferimento)
            )
            if registro is None:
                registro = RegistroEsiti(data_riferimento=data_riferimento)
                session.add(registro)
                session.flush()

            esito = EsitoConsegna(
                stato_esito=stato_esito,
                data_registrazione=datetime.now(),
                ordine_id=ordine_id,
                viaggio_id=viaggio_id,
                causale_id=causale_codice if stato_esito == StatoEsito.FALLITO else None,
                registro_id=registro.id,
            )
            session.add(esito)

            ordine.data_consegna = datetime.now()
            if stato_esito == StatoEsito.COMPLETATO:
                ordine.stato_ordine = StatoOrdine.COMPLETATO
            else:
                ordine.stato_ordine = StatoOrdine.RICEVUTO
                ordine.viaggio_id = None

            session.commit()
            return RisultatoRegistrazioneEsito(ok=True, esito_id=esito.id)

    def carica_prova_documentale(
        self,
        esito_id: int,
        nome_file: str,
        percorso_file_originale: str,
        tipo_file: str,
    ) -> RisultatoOperazione:
        """RF18: copia FISICAMENTE il file (non solo il riferimento al percorso originale) in
        cartella_allegati/<esito_id>/<nome_file>, cosi' la prova documentale non si perde se
        l'utente sposta o cancella il file sorgente dopo il caricamento.
        """
        with self.session_factory() as session:
            esito = session.get(EsitoConsegna, esito_id)
            if esito is None:
                return RisultatoOperazione(ok=False, motivo=f"Esito '{esito_id}' non trovato")
            if esito.stato_esito != StatoEsito.FALLITO:
                return RisultatoOperazione(
                    ok=False, motivo="Le prove documentali si allegano solo a un esito Fallito"
                )

            origine = Path(percorso_file_originale)
            if not origine.is_file():
                return RisultatoOperazione(ok=False, motivo=f"File non trovato: {percorso_file_originale}")

            # Path(...).name scarta qualunque componente di percorso (".." o assoluto incluso):
            # previene path traversal / scrittura fuori da cartella_allegati (RF18 riceve un
            # nome_file che in futuro arrivera' da input utente via GUI, non ancora vincolato qui).
            nome_base = Path(nome_file).name
            if not nome_base:
                return RisultatoOperazione(ok=False, motivo="Nome file non valido")

            cartella_esito = self.cartella_allegati / str(esito_id)
            cartella_esito.mkdir(parents=True, exist_ok=True)
            # Prefisso univoco: due prove caricate con lo stesso nome file (es. "foto.jpg" da
            # fotocamere diverse) non devono sovrascriversi silenziosamente sul disco.
            destinazione = cartella_esito / f"{uuid.uuid4().hex[:8]}_{nome_base}"
            shutil.copy2(origine, destinazione)

            try:
                session.add(
                    Allegato(
                        nome_file=nome_file,
                        percorso_file=str(destinazione),
                        tipo_file=tipo_file,
                        data_caricamento=datetime.now(),
                        esito_id=esito_id,
                    )
                )
                session.commit()
            except Exception:
                destinazione.unlink(missing_ok=True)
                raise
            return RisultatoOperazione(ok=True)

    def elenca_consegne_in_transito(self) -> list[ViaggioInTransito]:
        """RF15: schermata riepilogativa dei viaggi attualmente in transito (IN_CORSO), con i
        rispettivi ordini a bordo.
        """
        with self.session_factory() as session:
            viaggi = session.scalars(
                select(Viaggio)
                .where(Viaggio.stato_viaggio == StatoViaggio.IN_CORSO)
                .options(selectinload(Viaggio.ordini))
            ).all()
            return [
                ViaggioInTransito(
                    id=viaggio.id,
                    data_partenza_prevista=viaggio.data_partenza_prevista,
                    ordini=[
                        OrdineInTransitoVista(
                            id=ordine.id,
                            cliente=ordine.cliente,
                            indirizzo=ordine.indirizzo,
                            comune=ordine.comune,
                            categoria_consegna=ordine.categoria_consegna,
                            stato_ordine=ordine.stato_ordine,
                        )
                        for ordine in viaggio.ordini
                    ],
                )
                for viaggio in viaggi
            ]

    def elenco_causali_fallimento(self) -> list[tuple[str, str]]:
        """Coppie (codice, descrizione) di CausaleFallimento (GUI: popola il selettore "Causale
        del fallimento" del modale Registra esito). E' una tabella di lookup a se stante nel
        modello dati - a differenza di negozio_partner, che e' testo libero su Ordine - quindi qui
        i valori vengono da una vera query sulla tabella, non da un DISTINCT su un campo esistente.
        Nessun meccanismo di seed automatico: su un DB nuovo la lista puo' essere vuota finche' non
        vengono inserite causali (es. scripts/seed_dati_finti.py in sviluppo), fuori scope qui.
        """
        with self.session_factory() as session:
            righe = session.execute(
                select(CausaleFallimento.codice, CausaleFallimento.descrizione).order_by(
                    CausaleFallimento.descrizione
                )
            ).all()
            return [(r[0], r[1]) for r in righe]

    def elenca_esiti(
        self,
        ricerca: str | None = None,
        filtro_esito: str | list[str] = FILTRO_TUTTI,
        filtro_data: date | None = None,
        pagina: int = 1,
        dimensione_pagina: int = 20,
        decrescente: bool = True,
    ) -> PaginaEsiti:
        """Elenco filtrato/ordinato/paginato dello storico esiti (tab "Esiti" di Ordini).
        Filtri: ricerca testuale (cliente, causale o id ordine), filtro esito (Tutti/Completato/
        Fallito), filtro su un giorno esatto di data_registrazione. Ordinato per data_registrazione,
        decrescente di default (il piu' recente prima) - a differenza di visualizza_ordini, qui non
        esistono righe "senza data" da mettere sempre in coda: data_registrazione e' sempre
        valorizzata alla creazione dell'EsitoConsegna. Stesso pattern di filtro/paginazione
        Python-side di GestoreLogistica.visualizza_ordini, per coerenza tra le due liste della
        stessa pagina."""
        with self.session_factory() as session:
            righe_grezze = session.execute(
                select(
                    EsitoConsegna.id,
                    EsitoConsegna.ordine_id,
                    Ordine.cliente,
                    Ordine.indirizzo,
                    Ordine.comune,
                    Ordine.peso,
                    Ordine.volume_cargo,
                    EsitoConsegna.stato_esito,
                    EsitoConsegna.causale_id,
                    CausaleFallimento.descrizione,
                    EsitoConsegna.data_registrazione,
                )
                .join(Ordine, Ordine.id == EsitoConsegna.ordine_id)
                .outerjoin(CausaleFallimento, CausaleFallimento.codice == EsitoConsegna.causale_id)
                .order_by(EsitoConsegna.data_registrazione.desc() if decrescente else EsitoConsegna.data_registrazione)
            ).all()

            righe = [
                EsitoVista(
                    id=r[0],
                    ordine_id=r[1],
                    cliente=r[2],
                    indirizzo=f"{r[3]}, {r[4]}",
                    peso=r[5],
                    volume_cargo=r[6],
                    esito=r[7].value,
                    causale_codice=r[8],
                    causale=r[9],
                    data_registrazione=r[10],
                )
                for r in righe_grezze
            ]

            valori_esito = _normalizza_filtro_multiplo(filtro_esito, FILTRO_TUTTI)
            if valori_esito:
                righe = [r for r in righe if r.esito in valori_esito]

            if filtro_data is not None:
                righe = [r for r in righe if r.data_registrazione.date() == filtro_data]

            if ricerca:
                termine = ricerca.strip().lower()
                if termine:
                    righe = [
                        r
                        for r in righe
                        if termine in r.ordine_id.lower()
                        or termine in r.cliente.lower()
                        or (r.causale is not None and termine in r.causale.lower())
                    ]

            totale = len(righe)
            if dimensione_pagina > 0:
                inizio = max(pagina - 1, 0) * dimensione_pagina
                righe = righe[inizio : inizio + dimensione_pagina]

            return PaginaEsiti(esiti=righe, totale=totale)

    def _report_gia_generato(self, session: Session, registro_id: int) -> bool:
        """Guardia condivisa da modifica_esito/elimina_esito: se il report giornaliero (RF19) e'
        gia' stato generato per il RegistroEsiti di questo esito, i conteggi nel PDF diventerebbero
        disallineati rispetto al DB - piu' sicuro rifiutare la modifica che rigenerare il report
        automaticamente (nessuna RF lo richiede)."""
        return (
            session.scalar(select(ReportConsuntivo).where(ReportConsuntivo.registro_id == registro_id))
            is not None
        )

    def modifica_esito(
        self,
        esito_id: int,
        nuovo_stato_esito: StatoEsito,
        causale_codice: str | None = None,
    ) -> RisultatoRegistrazioneEsito:
        """Corregge un EsitoConsegna gia' registrato (GUI: matita sulla tab Esiti). A differenza
        di registra_esito (che parte sempre da un ordine "pulito" su un viaggio IN_CORSO), qui
        l'ordine puo' essere gia' avanzato per conto proprio nel frattempo (ripianificato dopo un
        Fallito, o rimasto Completato) - ogni cambio di verso e' quindi ammesso solo se lo stato
        attuale dell'ordine e' ancora esattamente quello che QUESTO esito gli aveva impresso,
        altrimenti si rifiuta invece di sovrascrivere alla cieca uno stato nel frattempo diventato
        indipendente (stesso principio difensivo gia' usato per il "viaggio zombie" in
        logistica/gestore_logistica.py)."""
        with self.session_factory() as session:
            esito = session.get(EsitoConsegna, esito_id)
            if esito is None:
                return RisultatoRegistrazioneEsito(ok=False, motivo=f"Esito '{esito_id}' non trovato")

            if self._report_gia_generato(session, esito.registro_id):
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo="Il report giornaliero per questa data e' gia' stato generato"
                )

            if nuovo_stato_esito == StatoEsito.FALLITO and causale_codice is None:
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo="Causale obbligatoria per un esito Fallito"
                )
            if nuovo_stato_esito == StatoEsito.FALLITO and session.get(CausaleFallimento, causale_codice) is None:
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo=f"Causale '{causale_codice}' non trovata"
                )

            ordine = session.get(Ordine, esito.ordine_id)
            cambia_verso = nuovo_stato_esito != esito.stato_esito
            if cambia_verso:
                if esito.stato_esito == StatoEsito.COMPLETATO:
                    # Completato -> Fallito: l'ordine deve essere ancora esattamente com'era
                    # subito dopo la registrazione originale (agganciato a QUESTO viaggio).
                    if ordine.viaggio_id != esito.viaggio_id or ordine.stato_ordine != StatoOrdine.COMPLETATO:
                        return RisultatoRegistrazioneEsito(
                            ok=False, motivo="L'ordine e' cambiato dopo la registrazione, non piu' modificabile"
                        )
                    ordine.stato_ordine = StatoOrdine.RICEVUTO
                    ordine.viaggio_id = None
                else:
                    # Fallito -> Completato: l'ordine deve essere ancora quello ripianificato da
                    # RF17 (sganciato da qualunque viaggio) - se nel frattempo e' stato riassegnato
                    # a un nuovo viaggio (RF10-13) o ha gia' un esito piu' recente, riagganciarlo
                    # ora al vecchio viaggio lo strapperebbe da quello nuovo.
                    if ordine.viaggio_id is not None or ordine.stato_ordine != StatoOrdine.RICEVUTO:
                        return RisultatoRegistrazioneEsito(
                            ok=False, motivo="L'ordine e' stato ripianificato nel frattempo, non piu' modificabile"
                        )
                    ordine.viaggio_id = esito.viaggio_id
                    ordine.stato_ordine = StatoOrdine.COMPLETATO

            esito.stato_esito = nuovo_stato_esito
            esito.causale_id = causale_codice if nuovo_stato_esito == StatoEsito.FALLITO else None
            session.commit()
            return RisultatoRegistrazioneEsito(ok=True, esito_id=esito.id)

    def elimina_esito(self, esito_id: int) -> RisultatoOperazione:
        """Elimina un EsitoConsegna gia' registrato (GUI: cestino sulla tab Esiti), incluse le
        eventuali prove documentali allegate (righe Allegato + file fisici in
        cartella_allegati/<esito_id>/ - senza questo, il DELETE fallirebbe comunque per il vincolo
        di chiave esterna Allegato.esito_id). Stessa guardia di modifica_esito su ordine/report gia'
        avanzati, stesso motivo."""
        with self.session_factory() as session:
            esito = session.get(EsitoConsegna, esito_id)
            if esito is None:
                return RisultatoOperazione(ok=False, motivo=f"Esito '{esito_id}' non trovato")

            if self._report_gia_generato(session, esito.registro_id):
                return RisultatoOperazione(
                    ok=False, motivo="Il report giornaliero per questa data e' gia' stato generato"
                )

            ordine = session.get(Ordine, esito.ordine_id)
            if esito.stato_esito == StatoEsito.COMPLETATO:
                if ordine.viaggio_id != esito.viaggio_id or ordine.stato_ordine != StatoOrdine.COMPLETATO:
                    return RisultatoOperazione(
                        ok=False, motivo="L'ordine e' cambiato dopo la registrazione, non piu' eliminabile"
                    )
                # Ripristina lo stato immediatamente precedente alla consegna: ancora agganciato
                # al viaggio, non piu' "consegnato".
                ordine.stato_ordine = StatoOrdine.PIANIFICATO
            # Se Fallito, l'ordine e' gia' stato ripianificato da RF17 al momento della
            # registrazione originale - eliminare questo record storico non lo tocca.

            allegati = session.scalars(select(Allegato).where(Allegato.esito_id == esito_id)).all()
            for allegato_riga in allegati:
                session.delete(allegato_riga)
            cartella_esito = self.cartella_allegati / str(esito_id)
            if cartella_esito.is_dir():
                shutil.rmtree(cartella_esito)

            session.delete(esito)
            session.commit()
            return RisultatoOperazione(ok=True)

    def elenco_allegati(self, esito_id: int) -> list[AllegatoVista]:
        """Prove documentali gia' caricate per un esito (GUI: modale di modifica su un esito
        Fallito, mostra cosa e' gia' stato allegato prima di permettere di aggiungerne altre)."""
        with self.session_factory() as session:
            allegati = session.scalars(
                select(Allegato).where(Allegato.esito_id == esito_id).order_by(Allegato.data_caricamento)
            ).all()
            return [
                AllegatoVista(
                    id=a.id,
                    nome_file=a.nome_file,
                    percorso_file=a.percorso_file,
                    tipo_file=a.tipo_file,
                    data_caricamento=a.data_caricamento,
                )
                for a in allegati
            ]


def _genera_pdf(
    percorso_file: Path,
    data_riferimento: datetime,
    conteggio_per_negozio: dict[str, dict[str, int]],
    ordini_consegnati: int,
    ordini_falliti: int,
) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Report Consuntivo Consegne", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Data: {data_riferimento:%d/%m/%Y}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        8,
        f"Consegne completate: {ordini_consegnati}  -  Consegne fallite: {ordini_falliti}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Dettaglio per negozio partner", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for negozio, conteggi in sorted(conteggio_per_negozio.items()):
        pdf.cell(
            0,
            7,
            f"{negozio}: completati {conteggi['completati']}, falliti {conteggi['falliti']}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.output(str(percorso_file))
