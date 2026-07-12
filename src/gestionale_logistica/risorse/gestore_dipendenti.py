from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import Dipendente

dipendente = CRUDBase[Dipendente](Dipendente)


@dataclass
class RisultatoOperazioneDipendente:
    ok: bool
    dipendente_id: str | None = None
    motivo: str | None = None


class GestoreDipendenti:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def inserisci_dipendente(
        self,
        id_: str,
        nome: str,
        cognome: str,
        codice_fiscale: str,
        data_assunzione: datetime,
        flg_certificazione_gas: bool = False,
    ) -> RisultatoOperazioneDipendente:
        """RF1: registra un nuovo dipendente. Rifiuta id o codice_fiscale gia' in uso (Fix 7)."""
        with self.session_factory() as session:
            if session.get(Dipendente, id_) is not None:
                return RisultatoOperazioneDipendente(ok=False, motivo=f"Dipendente '{id_}' gia' esistente")
            if session.scalar(select(Dipendente).where(Dipendente.codice_fiscale == codice_fiscale)) is not None:
                return RisultatoOperazioneDipendente(
                    ok=False, motivo=f"Codice fiscale '{codice_fiscale}' gia' registrato"
                )

            session.add(
                Dipendente(
                    id=id_,
                    nome=nome,
                    cognome=cognome,
                    codice_fiscale=codice_fiscale,
                    data_assunzione=data_assunzione,
                    data_licenziamento=None,
                    flg_attivo=True,
                    flg_certificazione_gas=flg_certificazione_gas,
                )
            )
            session.commit()
            return RisultatoOperazioneDipendente(ok=True, dipendente_id=id_)
