from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Viaggio

camion = CRUDBase[Camion](Camion)


@dataclass
class RisultatoOperazioneCamion:
    ok: bool
    camion_id: str | None = None
    motivo: str | None = None


class GestoreCamion:
    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self.session_factory = session_factory

    def inserisci_camion(
        self,
        id_: str,
        targa: str,
        tipo_mezzo: str,
        data_acquisizione: datetime,
        peso_massimo: float,
        volume_massimo: float,
        flg_sponda_idraulica: bool = False,
    ) -> RisultatoOperazioneCamion:
        """RF4: registra un nuovo camion. Rifiuta id o targa gia' in uso."""
        with self.session_factory() as session:
            if session.get(Camion, id_) is not None:
                return RisultatoOperazioneCamion(ok=False, motivo=f"Camion '{id_}' gia' esistente")
            if session.scalar(select(Camion).where(Camion.targa == targa)) is not None:
                return RisultatoOperazioneCamion(ok=False, motivo=f"Targa '{targa}' gia' registrata")

            session.add(
                Camion(
                    id=id_,
                    targa=targa,
                    tipo_mezzo=tipo_mezzo,
                    peso_massimo=peso_massimo,
                    volume_massimo=volume_massimo,
                    flg_sponda_idraulica=flg_sponda_idraulica,
                    data_acquisizione=data_acquisizione,
                    data_dismissione=None,
                    flg_attivo=True,
                )
            )
            session.commit()
            return RisultatoOperazioneCamion(ok=True, camion_id=id_)

    def modifica_camion(
        self,
        id_: str,
        targa: str | None = None,
        tipo_mezzo: str | None = None,
        peso_massimo: float | None = None,
        volume_massimo: float | None = None,
        flg_sponda_idraulica: bool | None = None,
    ) -> RisultatoOperazioneCamion:
        """RF5: aggiorna i dati tecnici di un camion esistente (es. aggiunta della sponda
        idraulica). L'identificativo di sistema (id) non e' mai modificabile."""
        with self.session_factory() as session:
            mezzo = session.get(Camion, id_)
            if mezzo is None:
                return RisultatoOperazioneCamion(ok=False, motivo=f"Camion '{id_}' non trovato")

            if targa is not None and targa != mezzo.targa:
                if session.scalar(select(Camion).where(Camion.targa == targa)) is not None:
                    return RisultatoOperazioneCamion(ok=False, motivo=f"Targa '{targa}' gia' registrata")
                mezzo.targa = targa
            if tipo_mezzo is not None:
                mezzo.tipo_mezzo = tipo_mezzo
            if peso_massimo is not None:
                mezzo.peso_massimo = peso_massimo
            if volume_massimo is not None:
                mezzo.volume_massimo = volume_massimo
            if flg_sponda_idraulica is not None:
                mezzo.flg_sponda_idraulica = flg_sponda_idraulica

            session.commit()
            return RisultatoOperazioneCamion(ok=True, camion_id=id_)

    def disattiva_camion(
        self, id_: str, data_dismissione: datetime | None = None
    ) -> RisultatoOperazioneCamion:
        """RF6: soft delete - il camion resta a database (storico, RF8) ma flg_attivo=False lo
        esclude dalle risorse attive (RF7) e dai nuovi viaggi (verifica_idoneita_risorsa),
        mantenendo intatta l'integrita' referenziale dei viaggi passati. Disattiva a cascata anche
        le ComposizioneSquadra attive che lo contengono - stesso motivo di
        GestoreDipendenti.licenzia_dipendente(): senza, avvia_composizione_viaggio (RF10) le
        riterrebbe ancora valide, creando un Viaggio IN_COMPOSIZIONE bloccato indefinitamente.

        La cascata da sola non basta per un Viaggio IN_COMPOSIZIONE aperto *prima* della
        dismissione (stesso gap di GestoreDipendenti.licenzia_dipendente(), vedi li' per il
        dettaglio) - la dismissione viene percio' rifiutata a monte se il camion e' coinvolto in
        un Viaggio IN_COMPOSIZIONE o IN_CORSO."""
        with self.session_factory() as session:
            mezzo = session.get(Camion, id_)
            if mezzo is None:
                return RisultatoOperazioneCamion(ok=False, motivo=f"Camion '{id_}' non trovato")
            if not mezzo.flg_attivo:
                return RisultatoOperazioneCamion(ok=False, motivo="Camion gia' fuori servizio")

            composizioni = session.scalars(
                select(ComposizioneSquadra).where(ComposizioneSquadra.camion_id == id_)
            ).all()
            if composizioni:
                viaggio_bloccante = session.scalar(
                    select(Viaggio.id).where(
                        Viaggio.composizione_id.in_([c.id_composizione for c in composizioni]),
                        Viaggio.stato_viaggio.in_([StatoViaggio.IN_COMPOSIZIONE, StatoViaggio.IN_CORSO]),
                    )
                )
                if viaggio_bloccante is not None:
                    return RisultatoOperazioneCamion(
                        ok=False,
                        motivo=(
                            f"Impossibile dismettere: coinvolto nel viaggio '{viaggio_bloccante}', "
                            "ancora in composizione o in corso"
                        ),
                    )

            mezzo.flg_attivo = False
            mezzo.data_dismissione = data_dismissione or datetime.now()

            for composizione in composizioni:
                if composizione.flg_attiva:
                    composizione.flg_attiva = False

            session.commit()
            return RisultatoOperazioneCamion(ok=True, camion_id=id_)
