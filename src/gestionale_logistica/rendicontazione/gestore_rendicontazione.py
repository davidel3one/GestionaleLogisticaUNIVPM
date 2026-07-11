from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import StatoOrdine
from gestionale_logistica.database.models import (
    Allegato,
    CausaleFallimento,
    EsitoConsegna,
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
STATI_RENDICONTABILI = (StatoOrdine.COMPLETATO, StatoOrdine.FALLITO)


@dataclass
class RisultatoGenerazioneReport:
    generato: bool
    report_id: int | None = None
    percorso_file: str | None = None
    motivo: str | None = None


class GestoreRendicontazione:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        cartella_output: Path = CARTELLA_REPORT_DEFAULT,
    ) -> None:
        self.session_factory = session_factory
        self.cartella_output = cartella_output

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
            if registro_esistente is not None:
                report_esistente = session.scalar(
                    select(ReportConsuntivo.id).where(ReportConsuntivo.registro_id == registro_esistente.id)
                )
                if report_esistente is not None:
                    return RisultatoGenerazioneReport(
                        generato=False, motivo="Report gia' generato per questa data"
                    )

            viaggi_del_giorno = session.scalars(
                select(Viaggio).where(
                    Viaggio.data_partenza_prevista >= data_riferimento,
                    Viaggio.data_partenza_prevista < fine_giorno,
                )
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
