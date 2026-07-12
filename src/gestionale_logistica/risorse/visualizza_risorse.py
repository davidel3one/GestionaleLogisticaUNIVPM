from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.models import Camion, Dipendente


@dataclass
class DipendenteVista:
    id: str
    nome: str
    cognome: str
    codice_fiscale: str
    flg_attivo: bool
    flg_certificazione_gas: bool


@dataclass
class CamionVista:
    id: str
    targa: str
    tipo_mezzo: str
    flg_attivo: bool
    flg_sponda_idraulica: bool


@dataclass
class ElencoRisorse:
    dipendenti: list[DipendenteVista]
    camion: list[CamionVista]


def _vista_dipendente(d: Dipendente) -> DipendenteVista:
    return DipendenteVista(
        id=d.id,
        nome=d.nome,
        cognome=d.cognome,
        codice_fiscale=d.codice_fiscale,
        flg_attivo=d.flg_attivo,
        flg_certificazione_gas=d.flg_certificazione_gas,
    )


def _vista_camion(c: Camion) -> CamionVista:
    return CamionVista(
        id=c.id,
        targa=c.targa,
        tipo_mezzo=c.tipo_mezzo,
        flg_attivo=c.flg_attivo,
        flg_sponda_idraulica=c.flg_sponda_idraulica,
    )


class VisualizzaStoricoRisorse:
    """RF8: elenca tutte le risorse transitate in azienda, inclusi dipendenti licenziati e mezzi
    dismessi (nome della classe preso dal diagramma EA - vedi modello-ea.md, Fix 6)."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def elenca(self) -> ElencoRisorse:
        with self.session_factory() as session:
            dipendenti = session.scalars(select(Dipendente)).all()
            camion = session.scalars(select(Camion)).all()
            return ElencoRisorse(
                dipendenti=[_vista_dipendente(d) for d in dipendenti],
                camion=[_vista_camion(c) for c in camion],
            )
