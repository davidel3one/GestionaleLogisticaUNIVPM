from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Viaggio


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


class VisualizzaConsegneInTransito:
    """RF15: schermata riepilogativa dei viaggi attualmente in transito (IN_CORSO), con i
    rispettivi ordini a bordo.
    """

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def elenca(self) -> list[ViaggioInTransito]:
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
