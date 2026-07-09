import csv
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Ordine, Viaggio
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
