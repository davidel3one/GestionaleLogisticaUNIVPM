from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Dipendente, Squadra

squadra = CRUDBase[Squadra](Squadra)
composizione_squadra = CRUDBase[ComposizioneSquadra](ComposizioneSquadra)


@dataclass
class RisultatoOperazioneSquadra:
    ok: bool
    squadra_id: str | None = None
    motivo: str | None = None


@dataclass
class RisultatoOperazioneComposizione:
    ok: bool
    composizione_id: str | None = None
    motivo: str | None = None


class GestoreSquadre:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def crea_squadra(self, id_: str, data_creazione: datetime | None = None) -> RisultatoOperazioneSquadra:
        """Registra una nuova Squadra, senza ancora una composizione (camion+2 dipendenti)."""
        with self.session_factory() as session:
            if session.get(Squadra, id_) is not None:
                return RisultatoOperazioneSquadra(ok=False, motivo=f"Squadra '{id_}' gia' esistente")

            session.add(
                Squadra(id=id_, flg_attiva=True, data_creazione=data_creazione or datetime.now())
            )
            session.commit()
            return RisultatoOperazioneSquadra(ok=True, squadra_id=id_)

    def apri_composizione(
        self,
        id_composizione: str,
        squadra_id: str,
        camion_id: str,
        dipendente_1_id: str,
        dipendente_2_id: str,
        data_inizio_validita: datetime | None = None,
    ) -> RisultatoOperazioneComposizione:
        """RF10-RF13 (precondizione): storicizza una ComposizioneSquadra (camion + 2 dipendenti)
        per una Squadra attiva. Richiede che camion e dipendenti siano idonei alla composizione
        (flg_attivo, RF3/RF6) - non chiama verifica_idoneita_risorsa() perche' quella valuta
        l'idoneita' rispetto alla categoria di un Ordine specifico, che qui non esiste ancora."""
        with self.session_factory() as session:
            if session.get(ComposizioneSquadra, id_composizione) is not None:
                return RisultatoOperazioneComposizione(
                    ok=False, motivo=f"Composizione '{id_composizione}' gia' esistente"
                )

            squadra_obj = session.get(Squadra, squadra_id)
            if squadra_obj is None:
                return RisultatoOperazioneComposizione(ok=False, motivo=f"Squadra '{squadra_id}' non trovata")
            if not squadra_obj.flg_attiva:
                return RisultatoOperazioneComposizione(ok=False, motivo="Squadra non attiva")

            camion = session.get(Camion, camion_id)
            if camion is None:
                return RisultatoOperazioneComposizione(ok=False, motivo=f"Camion '{camion_id}' non trovato")
            if not camion.flg_attivo:
                return RisultatoOperazioneComposizione(ok=False, motivo="Camion non e' piu' in servizio")

            if dipendente_1_id == dipendente_2_id:
                return RisultatoOperazioneComposizione(
                    ok=False, motivo="I due dipendenti della squadra devono essere distinti"
                )

            for dipendente_id in (dipendente_1_id, dipendente_2_id):
                dipendente = session.get(Dipendente, dipendente_id)
                if dipendente is None:
                    return RisultatoOperazioneComposizione(
                        ok=False, motivo=f"Dipendente '{dipendente_id}' non trovato"
                    )
                if not dipendente.flg_attivo:
                    return RisultatoOperazioneComposizione(
                        ok=False, motivo=f"Dipendente '{dipendente_id}' non e' piu' in servizio"
                    )

            session.add(
                ComposizioneSquadra(
                    id_composizione=id_composizione,
                    squadra_id=squadra_id,
                    camion_id=camion_id,
                    dipendente_1_id=dipendente_1_id,
                    dipendente_2_id=dipendente_2_id,
                    data_inizio_validita=data_inizio_validita or datetime.now(),
                    data_fine_validita=None,
                    flg_attiva=True,
                )
            )
            session.commit()
            return RisultatoOperazioneComposizione(ok=True, composizione_id=id_composizione)
