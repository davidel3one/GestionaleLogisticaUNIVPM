from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import ComposizioneSquadra, Dipendente

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

    def modifica_dipendente(
        self,
        id_: str,
        nome: str | None = None,
        cognome: str | None = None,
        flg_certificazione_gas: bool | None = None,
    ) -> RisultatoOperazioneDipendente:
        """RF2: aggiorna dati anagrafici/certificazioni di un dipendente esistente. L'identificativo
        di sistema (id) non e' mai modificabile - non a caso non compare tra i campi aggiornabili."""
        with self.session_factory() as session:
            dip = session.get(Dipendente, id_)
            if dip is None:
                return RisultatoOperazioneDipendente(ok=False, motivo=f"Dipendente '{id_}' non trovato")

            if nome is not None:
                dip.nome = nome
            if cognome is not None:
                dip.cognome = cognome
            if flg_certificazione_gas is not None:
                dip.flg_certificazione_gas = flg_certificazione_gas

            session.commit()
            return RisultatoOperazioneDipendente(ok=True, dipendente_id=id_)

    def licenzia_dipendente(
        self, id_: str, data_licenziamento: datetime | None = None
    ) -> RisultatoOperazioneDipendente:
        """RF3: soft delete - il dipendente resta a database (storico, RF8) ma flg_attivo=False lo
        esclude dalle risorse attive (RF7) e dai nuovi viaggi (verifica_idoneita_risorsa). Disattiva
        a cascata anche le ComposizioneSquadra attive che lo contengono (dipendente_1/dipendente_2):
        senza, avvia_composizione_viaggio (RF10) le riterrebbe ancora valide (controlla solo
        composizione.flg_attiva), creando un Viaggio IN_COMPOSIZIONE che nessun ordine potrebbe mai
        raggiungere (verifica_idoneita_risorsa rifiuta sempre) e che chiudi_composizione_viaggio non
        potrebbe mai chiudere (richiede almeno un ordine) - uno stato "zombie" indefinito."""
        with self.session_factory() as session:
            dip = session.get(Dipendente, id_)
            if dip is None:
                return RisultatoOperazioneDipendente(ok=False, motivo=f"Dipendente '{id_}' non trovato")
            if not dip.flg_attivo:
                return RisultatoOperazioneDipendente(ok=False, motivo="Dipendente gia' licenziato")

            dip.flg_attivo = False
            dip.data_licenziamento = data_licenziamento or datetime.now()

            composizioni_da_disattivare = session.scalars(
                select(ComposizioneSquadra).where(
                    ComposizioneSquadra.flg_attiva.is_(True),
                    or_(
                        ComposizioneSquadra.dipendente_1_id == id_,
                        ComposizioneSquadra.dipendente_2_id == id_,
                    ),
                )
            ).all()
            for composizione in composizioni_da_disattivare:
                composizione.flg_attiva = False

            session.commit()
            return RisultatoOperazioneDipendente(ok=True, dipendente_id=id_)
