import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Viaggio

camion = CRUDBase[Camion](Camion)

STATO_ATTIVO = "Attivo"
STATO_IN_VIAGGIO = "In viaggio"
STATO_DISMESSO = "Dismesso"
FILTRO_TUTTI = "Tutti"

# Formato standard targhe italiane in uso dal 1994 (2 lettere, 3 cifre, 2 lettere, es. AB123CD).
# Solo controllo di formato, come CODICE_FISCALE_REGEX in gestore_dipendenti.py - non copre targhe
# storiche/speciali (moto, rimorchi, ecc.), fuori scope qui.
TARGA_REGEX = re.compile(r"^[A-Za-z]{2}[0-9]{3}[A-Za-z]{2}$")

# Le uniche 3 categorie viste nel mockup (tabella Camion): non un vincolo del modello (tipo_mezzo
# e' una stringa libera a DB), solo il set iniziale suggerito nella tendina "Tipo mezzo" del
# modale Aggiungi - si somma ai valori gia' realmente in uso (vedi _opzioni_tipo_mezzo in
# gui/pages/camion.py), cosi' la tendina non parte mai vuota su un DB nuovo.
TIPO_FURGONE = "Furgone"
TIPO_MOTRICE = "Motrice"
TIPO_BILICO = "Bilico"
TIPI_MEZZO_NOTI = [TIPO_FURGONE, TIPO_MOTRICE, TIPO_BILICO]


@dataclass
class RisultatoOperazioneCamion:
    ok: bool
    camion_id: str | None = None
    motivo: str | None = None


@dataclass
class CamionVista:
    id: str
    targa: str
    tipo_mezzo: str
    peso_massimo: float
    volume_massimo: float
    flg_sponda_idraulica: bool
    data_acquisizione: datetime
    stato: str


@dataclass
class PaginaCamion:
    """Pagina di risultati di visualizza_camion: solo la fetta richiesta + il totale filtrato."""

    camion: list[CamionVista]
    totale: int


def _stato_derivato(flg_attivo: bool, in_viaggio: bool) -> str:
    """Stato mostrato in lista: Dismesso > In viaggio (solo IN_CORSO) > Attivo."""
    if not flg_attivo:
        return STATO_DISMESSO
    if in_viaggio:
        return STATO_IN_VIAGGIO
    return STATO_ATTIVO


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
        """RF4: registra un nuovo camion. Rifiuta targa mal formata, o id/targa gia' in uso."""
        if not TARGA_REGEX.match(targa):
            return RisultatoOperazioneCamion(ok=False, motivo=f"Targa '{targa}' non valida")
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
                if not TARGA_REGEX.match(targa):
                    return RisultatoOperazioneCamion(ok=False, motivo=f"Targa '{targa}' non valida")
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

    def riattiva_camion(self, id_: str) -> RisultatoOperazioneCamion:
        """Annulla una dismissione fatta per errore: rimette flg_attivo=True e azzera
        data_dismissione. Non riattiva le ComposizioneSquadra disattivate dalla dismissione (stessa
        scelta di GestoreDipendenti.riassumi_dipendente() - andrebbe rifatta l'assegnazione a una
        squadra esplicitamente, non si presume quale fosse quella giusta)."""
        with self.session_factory() as session:
            mezzo = session.get(Camion, id_)
            if mezzo is None:
                return RisultatoOperazioneCamion(ok=False, motivo=f"Camion '{id_}' non trovato")
            if mezzo.flg_attivo:
                return RisultatoOperazioneCamion(ok=False, motivo="Camion gia' in servizio")

            mezzo.flg_attivo = True
            mezzo.data_dismissione = None

            session.commit()
            return RisultatoOperazioneCamion(ok=True, camion_id=id_)

    def visualizza_camion(
        self,
        ricerca: str | None = None,
        filtro_tipo: str | None = None,
        filtro_stato: str = FILTRO_TUTTI,
        pagina: int = 1,
        dimensione_pagina: int = 20,
        decrescente: bool = False,
    ) -> PaginaCamion:
        """Elenco filtrato/ordinato/paginato dei camion. Filtri: ricerca testuale (targa/tipo
        mezzo), filtro tipo mezzo, filtro stato (Tutti/Attivo/In viaggio/Dismesso), ordinamento
        per data_acquisizione, paginazione server-side. Stato "In viaggio" calcolato con una sola
        query aggregata sui Viaggio IN_CORSO (niente N+1) - piu' semplice del corrispettivo in
        GestoreDipendenti: ComposizioneSquadra.camion_id e' una FK sola, non richiede unire due
        query come per i due dipendenti di una composizione."""
        with self.session_factory() as session:
            in_viaggio_ids = set(
                session.scalars(
                    select(ComposizioneSquadra.camion_id)
                    .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
                    .where(
                        ComposizioneSquadra.flg_attiva.is_(True),
                        Viaggio.stato_viaggio == StatoViaggio.IN_CORSO,
                    )
                ).all()
            )

            ordine = Camion.data_acquisizione.desc() if decrescente else Camion.data_acquisizione.asc()
            mezzi = session.scalars(select(Camion).order_by(ordine)).all()

            righe: list[CamionVista] = []
            for mezzo in mezzi:
                stato = _stato_derivato(mezzo.flg_attivo, mezzo.id in in_viaggio_ids)
                righe.append(
                    CamionVista(
                        id=mezzo.id,
                        targa=mezzo.targa,
                        tipo_mezzo=mezzo.tipo_mezzo,
                        peso_massimo=mezzo.peso_massimo,
                        volume_massimo=mezzo.volume_massimo,
                        flg_sponda_idraulica=mezzo.flg_sponda_idraulica,
                        data_acquisizione=mezzo.data_acquisizione,
                        stato=stato,
                    )
                )

            if filtro_tipo:
                righe = [r for r in righe if r.tipo_mezzo == filtro_tipo]

            if filtro_stato and filtro_stato != FILTRO_TUTTI:
                righe = [r for r in righe if r.stato == filtro_stato]

            if ricerca:
                termine = ricerca.strip().lower()
                if termine:
                    righe = [
                        r
                        for r in righe
                        if termine in r.targa.lower() or termine in r.tipo_mezzo.lower()
                    ]

            totale = len(righe)
            if dimensione_pagina > 0:
                inizio = max(pagina - 1, 0) * dimensione_pagina
                righe = righe[inizio : inizio + dimensione_pagina]

            return PaginaCamion(camion=righe, totale=totale)
