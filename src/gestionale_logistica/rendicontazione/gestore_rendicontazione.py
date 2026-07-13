import shutil
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

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

esito_consegna = CRUDBase[EsitoConsegna](EsitoConsegna)
causale_fallimento = CRUDBase[CausaleFallimento](CausaleFallimento)
registro_esiti = CRUDBase[RegistroEsiti](RegistroEsiti)
allegato = CRUDBase[Allegato](Allegato)
report_consuntivo = CRUDBase[ReportConsuntivo](ReportConsuntivo)

CARTELLA_REPORT_DEFAULT = Path("report")
CARTELLA_ALLEGATI_DEFAULT = Path("allegati")
STATI_RENDICONTABILI = (StatoOrdine.COMPLETATO, StatoOrdine.FALLITO)


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
        fine_giorno = data_riferimento + timedelta(days=1)

        with self.session_factory() as session:
            registro_esistente = session.scalar(
                select(RegistroEsiti).where(RegistroEsiti.data_riferimento == data_riferimento)
            )
            report_esistente = None
            if registro_esistente is not None:
                report_esistente = session.scalar(
                    select(ReportConsuntivo).where(ReportConsuntivo.registro_id == registro_esistente.id)
                )

            viaggi_del_giorno = session.scalars(
                select(Viaggio)
                .where(
                    Viaggio.data_partenza_prevista >= data_riferimento,
                    Viaggio.data_partenza_prevista < fine_giorno,
                )
                .options(selectinload(Viaggio.ordini))
            ).all()
            ordini_rendicontati = [
                o for v in viaggi_del_giorno for o in v.ordini if o.stato_ordine in STATI_RENDICONTABILI
            ]
            if not ordini_rendicontati:
                return RisultatoGenerazioneReport(
                    generato=False, motivo="Nessuna consegna da rendicontare per questa data"
                )

            conteggio_per_negozio: dict[str, dict[str, int]] = defaultdict(
                lambda: {"completati": 0, "falliti": 0}
            )
            for o in ordini_rendicontati:
                negozio = o.negozio_partner or "Non specificato"
                chiave = "completati" if o.stato_ordine == StatoOrdine.COMPLETATO else "falliti"
                conteggio_per_negozio[negozio][chiave] += 1

            ordini_consegnati = sum(v["completati"] for v in conteggio_per_negozio.values())
            ordini_falliti = sum(v["falliti"] for v in conteggio_per_negozio.values())
            negozi_partner = ", ".join(sorted(conteggio_per_negozio))

            if registro_esistente is None:
                registro_esistente = RegistroEsiti(data_riferimento=data_riferimento)
                session.add(registro_esistente)
                session.flush()

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
                report_esistente.ordini = ordini_rendicontati
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
            report.ordini = ordini_rendicontati
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
            if ordine.esito is not None:
                return RisultatoRegistrazioneEsito(ok=False, motivo="Ordine gia' associato a un esito")
            if ordine.viaggio is None or ordine.viaggio.stato_viaggio != StatoViaggio.IN_CORSO:
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo="L'ordine non e' su un viaggio in corso"
                )

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
