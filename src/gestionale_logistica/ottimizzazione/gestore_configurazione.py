from dataclasses import dataclass
from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import CategoriaConsegna
from gestionale_logistica.database.models import ConfigurazionePianificazione, TempoInstallazione
from gestionale_logistica.ottimizzazione.stima_durata import TEMPO_INSTALLAZIONE_MINUTI

ID_CONFIGURAZIONE = 1

ORA_PARTENZA_DEFAULT = time(8, 0)
ORE_LAVORO_DEFAULT = 8.0


@dataclass
class Configurazione:
    ora_partenza_default: time
    ore_lavoro: float
    tempi_installazione_minuti: dict[CategoriaConsegna, int]


class GestoreConfigurazione:
    """Vincoli di RF10-13 configurabili dall'admin dal modale Impostazioni di Pianificazione.

    Riga singola con bootstrap lazy: al primo `leggi()` su un DB senza configurazione,
    crea la riga con i default storici (stessi valori che prima erano hardcoded nelle
    costanti di stima_durata.py/*_tab.py) invece di richiedere una migrazione a parte.
    """

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def leggi(self) -> Configurazione:
        with self.session_factory() as session:
            riga = session.get(ConfigurazionePianificazione, ID_CONFIGURAZIONE)
            if riga is None:
                riga = ConfigurazionePianificazione(
                    id=ID_CONFIGURAZIONE,
                    ora_partenza_default=ORA_PARTENZA_DEFAULT,
                    ore_lavoro=ORE_LAVORO_DEFAULT,
                )
                session.add(riga)

            tempi = {t.categoria: t.minuti for t in session.scalars(select(TempoInstallazione))}
            for categoria in CategoriaConsegna:
                if categoria not in tempi:
                    minuti = TEMPO_INSTALLAZIONE_MINUTI[categoria]
                    session.add(TempoInstallazione(categoria=categoria, minuti=minuti))
                    tempi[categoria] = minuti

            session.commit()

            return Configurazione(
                ora_partenza_default=riga.ora_partenza_default,
                ore_lavoro=riga.ore_lavoro,
                tempi_installazione_minuti=tempi,
            )

    def aggiorna(
        self,
        ora_partenza_default: time,
        ore_lavoro: float,
        tempi_installazione_minuti: dict[CategoriaConsegna, int],
    ) -> None:
        with self.session_factory() as session:
            riga = session.get(ConfigurazionePianificazione, ID_CONFIGURAZIONE)
            if riga is None:
                riga = ConfigurazionePianificazione(id=ID_CONFIGURAZIONE)
                session.add(riga)
            riga.ora_partenza_default = ora_partenza_default
            riga.ore_lavoro = ore_lavoro

            for categoria, minuti in tempi_installazione_minuti.items():
                tempo = session.get(TempoInstallazione, categoria)
                if tempo is None:
                    session.add(TempoInstallazione(categoria=categoria, minuti=minuti))
                else:
                    tempo.minuti = minuti

            session.commit()
