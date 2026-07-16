from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import aliased, sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import (
    Camion,
    ComposizioneSquadra,
    Dipendente,
    Ordine,
    Squadra,
    Viaggio,
)

squadra = CRUDBase[Squadra](Squadra)
composizione_squadra = CRUDBase[ComposizioneSquadra](ComposizioneSquadra)

# Segnaposto usato quando una squadra non ha una composizione attiva da cui ricavare membri/camion.
MEMBRI_ASSENTI = "—"

# Stati derivati esposti dalla vista (usati anche come valori del filtro stato).
STATO_ATTIVA = "Attiva"
STATO_IN_VIAGGIO = "In viaggio"
STATO_NON_ATTIVA = "Non attiva"
FILTRO_TUTTE = "Tutte"


def _normalizza_filtro_multiplo(valore: str | list[str] | None, sentinella: str | None) -> set[str] | None:
    """Vedi _normalizza_filtro_multiplo in gestore_dipendenti.py: stessa logica, duplicata perche'
    i due gestori non condividono un modulo utils comune."""
    if valore is None or valore == sentinella:
        return None
    if isinstance(valore, str):
        return {valore}
    return set(valore) or None


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


@dataclass
class SquadraVista:
    id: str
    membri: str
    camion: str
    data_creazione: datetime
    stato: str
    flg_certificazione_gas: bool
    flg_sponda_idraulica: bool


@dataclass
class PaginaSquadre:
    """Pagina di risultati di visualizza_squadre: solo la fetta richiesta + il totale filtrato."""

    squadre: list[SquadraVista]
    totale: int


@dataclass
class ViaggioDiSquadraVista:
    id_viaggio: str
    n_ordini: int
    stato_viaggio: StatoViaggio
    data_partenza_prevista: datetime


@dataclass
class DettaglioSquadra:
    id: str
    membri: str
    camion: str
    stato: str
    viaggi: list[ViaggioDiSquadraVista]


def _stato_derivato(flg_attiva: bool, in_viaggio: bool) -> str:
    """Stato mostrato in lista/dettaglio: Non attiva > In viaggio (solo IN_CORSO) > Attiva."""
    if not flg_attiva:
        return STATO_NON_ATTIVA
    if in_viaggio:
        return STATO_IN_VIAGGIO
    return STATO_ATTIVA


def _select_composizioni_attive():
    """SELECT delle composizioni attive con targa e nomi dei 2 dipendenti gia' joinati, cosi'
    membri/camion si ricavano senza lazy-loading per riga (niente N+1). Include anche i due flag
    derivati mostrati in lista/dettaglio: `flg_sponda_idraulica` del camion e
    `flg_certificazione_gas` di almeno uno dei 2 dipendenti (basta un membro certificato perche'
    la squadra possa gestire ordini CertificazioneGas - stessa idoneita' gia' verificata da
    GestoreLogistica.verifica_idoneita_risorsa per RF11, qui solo esposta come colonna)."""
    dipendente_1 = aliased(Dipendente)
    dipendente_2 = aliased(Dipendente)
    return (
        select(
            ComposizioneSquadra.squadra_id,
            ComposizioneSquadra.data_inizio_validita,
            Camion.targa,
            dipendente_1.nome,
            dipendente_1.cognome,
            dipendente_2.nome,
            dipendente_2.cognome,
            ComposizioneSquadra.id_composizione,
            Camion.flg_sponda_idraulica,
            dipendente_1.flg_certificazione_gas,
            dipendente_2.flg_certificazione_gas,
        )
        .join(Camion, Camion.id == ComposizioneSquadra.camion_id)
        .join(dipendente_1, dipendente_1.id == ComposizioneSquadra.dipendente_1_id)
        .join(dipendente_2, dipendente_2.id == ComposizioneSquadra.dipendente_2_id)
        .where(ComposizioneSquadra.flg_attiva.is_(True))
    )


def _membri_da_riga(riga) -> str:
    return f"{riga[3]} {riga[4]}, {riga[5]} {riga[6]}"


def _certificazione_gas_da_riga(riga) -> bool:
    return bool(riga[9]) or bool(riga[10])


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

    def visualizza_squadre(
        self,
        ricerca: str | None = None,
        filtro_stato: str | list[str] = FILTRO_TUTTE,
        filtro_certificazione_gas: bool | None = None,
        filtro_sponda_idraulica: bool | None = None,
        pagina: int = 1,
        dimensione_pagina: int = 20,
        decrescente: bool = False,
    ) -> PaginaSquadre:
        """Elenco filtrato/ordinato/paginato delle squadre. Filtri: ricerca testuale (nome/cognome di
        uno dei 2 dipendenti o targa del camion della composizione attiva piu' recente), filtro stato
        (Tutte/Attiva/In viaggio/Non attiva), filtro certificazione gas/sponda idraulica (stesso
        pattern bool | None gia' usato da GestoreDipendenti.visualizza_dipendenti/
        GestoreCamion.visualizza_camion: None = nessun filtro), ordinamento per data_creazione,
        paginazione server-side. Lo stato "In viaggio" e' calcolato con una sola query aggregata
        sui Viaggio IN_CORSO (niente N+1); membri/camion con una sola query sulle composizioni
        attive."""
        with self.session_factory() as session:
            # Insieme delle squadre "in viaggio": composizione ATTIVA legata a un Viaggio IN_CORSO
            # (solo IN_CORSO). Una query per tutte le squadre, non una per riga.
            in_viaggio_ids = set(
                session.scalars(
                    select(ComposizioneSquadra.squadra_id)
                    .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
                    .where(
                        ComposizioneSquadra.flg_attiva.is_(True),
                        Viaggio.stato_viaggio == StatoViaggio.IN_CORSO,
                    )
                ).all()
            )

            # Composizione attiva piu' recente per squadra (max data_inizio_validita, tie-break su
            # id_composizione per un ordine deterministico coerente con dettaglio_squadra), con
            # membri+targa+i due flag derivati (sponda idraulica del camion, certificazione gas di
            # almeno uno dei 2 dipendenti).
            composizione_per_squadra: dict[str, tuple[datetime, str, str, str, bool, bool]] = {}
            for riga in session.execute(_select_composizioni_attive()).all():
                squadra_id = riga[0]
                corrente = composizione_per_squadra.get(squadra_id)
                if corrente is None or (riga[1], riga[7]) > (corrente[0], corrente[3]):
                    composizione_per_squadra[squadra_id] = (
                        riga[1],
                        _membri_da_riga(riga),
                        riga[2],
                        riga[7],
                        bool(riga[8]),
                        _certificazione_gas_da_riga(riga),
                    )

            ordine = Squadra.data_creazione.desc() if decrescente else Squadra.data_creazione.asc()
            squadre = session.scalars(select(Squadra).order_by(ordine)).all()

            righe: list[SquadraVista] = []
            for squadra_obj in squadre:
                dati = composizione_per_squadra.get(squadra_obj.id)
                membri = dati[1] if dati is not None else MEMBRI_ASSENTI
                camion = dati[2] if dati is not None else MEMBRI_ASSENTI
                sponda_idraulica = dati[4] if dati is not None else False
                certificazione_gas = dati[5] if dati is not None else False
                stato = _stato_derivato(squadra_obj.flg_attiva, squadra_obj.id in in_viaggio_ids)
                righe.append(
                    SquadraVista(
                        id=squadra_obj.id,
                        membri=membri,
                        camion=camion,
                        data_creazione=squadra_obj.data_creazione,
                        stato=stato,
                        flg_certificazione_gas=certificazione_gas,
                        flg_sponda_idraulica=sponda_idraulica,
                    )
                )

            valori_stato = _normalizza_filtro_multiplo(filtro_stato, FILTRO_TUTTE)
            if valori_stato:
                righe = [r for r in righe if r.stato in valori_stato]
            else:
                # "Tutte" nasconde le squadre Non attiva: su richiesta esplicita dell'utente
                # restano visibili in tabella solo scegliendo il filtro Stato "Non attiva" - stesso
                # trattamento esteso poi (2026-07-16) a GestoreDipendenti/GestoreCamion per Cessato/
                # Dismesso, inizialmente diverso qui (i tre gestori ora si comportano allo stesso modo).
                righe = [r for r in righe if r.stato != STATO_NON_ATTIVA]

            if ricerca:
                termine = ricerca.strip().lower()
                if termine:
                    righe = [
                        r for r in righe if termine in r.membri.lower() or termine in r.camion.lower()
                    ]

            if filtro_certificazione_gas is not None:
                righe = [r for r in righe if r.flg_certificazione_gas == filtro_certificazione_gas]
            if filtro_sponda_idraulica is not None:
                righe = [r for r in righe if r.flg_sponda_idraulica == filtro_sponda_idraulica]

            totale = len(righe)
            if dimensione_pagina > 0:
                inizio = max(pagina - 1, 0) * dimensione_pagina
                righe = righe[inizio : inizio + dimensione_pagina]

            return PaginaSquadre(squadre=righe, totale=totale)

    def dettaglio_squadra(self, squadra_id: str) -> DettaglioSquadra | None:
        """Dettaglio read-only di una squadra: membri/camion della composizione attiva piu' recente,
        stato derivato e tutti i viaggi (su TUTTE le composizioni della squadra) con il numero di
        ordini, ordinati per data_partenza_prevista decrescente. Ritorna None se la squadra non esiste."""
        with self.session_factory() as session:
            squadra_obj = session.get(Squadra, squadra_id)
            if squadra_obj is None:
                return None

            riga = session.execute(
                _select_composizioni_attive()
                .where(ComposizioneSquadra.squadra_id == squadra_id)
                .order_by(
                    ComposizioneSquadra.data_inizio_validita.desc(),
                    ComposizioneSquadra.id_composizione.desc(),
                )
            ).first()
            membri = _membri_da_riga(riga) if riga is not None else MEMBRI_ASSENTI
            camion = riga[2] if riga is not None else MEMBRI_ASSENTI

            in_viaggio = (
                session.scalar(
                    select(ComposizioneSquadra.squadra_id)
                    .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
                    .where(
                        ComposizioneSquadra.squadra_id == squadra_id,
                        ComposizioneSquadra.flg_attiva.is_(True),
                        Viaggio.stato_viaggio == StatoViaggio.IN_CORSO,
                    )
                )
                is not None
            )
            stato = _stato_derivato(squadra_obj.flg_attiva, in_viaggio)

            righe_viaggi = session.execute(
                select(
                    Viaggio.id,
                    Viaggio.stato_viaggio,
                    Viaggio.data_partenza_prevista,
                    func.count(Ordine.id),
                )
                .join(ComposizioneSquadra, ComposizioneSquadra.id_composizione == Viaggio.composizione_id)
                .outerjoin(Ordine, Ordine.viaggio_id == Viaggio.id)
                .where(ComposizioneSquadra.squadra_id == squadra_id)
                .group_by(Viaggio.id, Viaggio.stato_viaggio, Viaggio.data_partenza_prevista)
                .order_by(Viaggio.data_partenza_prevista.desc())
            ).all()
            viaggi = [
                ViaggioDiSquadraVista(
                    id_viaggio=riga_viaggio[0],
                    n_ordini=riga_viaggio[3],
                    stato_viaggio=riga_viaggio[1],
                    data_partenza_prevista=riga_viaggio[2],
                )
                for riga_viaggio in righe_viaggi
            ]

            return DettaglioSquadra(id=squadra_obj.id, membri=membri, camion=camion, stato=stato, viaggi=viaggi)

    def elimina_squadra(self, squadra_id: str) -> RisultatoOperazioneSquadra:
        """Soft-delete di una squadra: flg_attiva=False sulla squadra e a cascata sulle sue
        ComposizioneSquadra ancora attive. Rifiuta se una composizione della squadra e' legata a un
        Viaggio IN_CORSO (solo IN_CORSO blocca; IN_COMPOSIZIONE/PIANIFICATO no)."""
        with self.session_factory() as session:
            squadra_obj = session.get(Squadra, squadra_id)
            if squadra_obj is None:
                return RisultatoOperazioneSquadra(ok=False, motivo=f"Squadra '{squadra_id}' non trovata")
            if not squadra_obj.flg_attiva:
                return RisultatoOperazioneSquadra(ok=False, motivo="Squadra gia' non attiva")

            viaggio_bloccante = session.scalar(
                select(Viaggio.id)
                .join(ComposizioneSquadra, ComposizioneSquadra.id_composizione == Viaggio.composizione_id)
                .where(
                    ComposizioneSquadra.squadra_id == squadra_id,
                    Viaggio.stato_viaggio == StatoViaggio.IN_CORSO,
                )
            )
            if viaggio_bloccante is not None:
                return RisultatoOperazioneSquadra(
                    ok=False,
                    squadra_id=squadra_id,
                    motivo=f"Impossibile eliminare: coinvolta nel viaggio '{viaggio_bloccante}' in corso",
                )

            squadra_obj.flg_attiva = False
            composizioni = session.scalars(
                select(ComposizioneSquadra).where(
                    ComposizioneSquadra.squadra_id == squadra_id,
                    ComposizioneSquadra.flg_attiva.is_(True),
                )
            ).all()
            for composizione in composizioni:
                composizione.flg_attiva = False

            session.commit()
            return RisultatoOperazioneSquadra(ok=True, squadra_id=squadra_id)

    def riattiva_squadra(self, squadra_id: str) -> RisultatoOperazioneSquadra:
        """Annulla un'eliminazione fatta per errore: rimette flg_attiva=True sulla squadra. Non
        riattiva le ComposizioneSquadra disattivate dall'eliminazione (stessa scelta di
        GestoreDipendenti.riassumi_dipendente()/GestoreCamion.riattiva_camion() - andrebbe rifatta
        l'assegnazione camion+dipendenti esplicitamente, non si presume quale fosse quella giusta)."""
        with self.session_factory() as session:
            squadra_obj = session.get(Squadra, squadra_id)
            if squadra_obj is None:
                return RisultatoOperazioneSquadra(ok=False, motivo=f"Squadra '{squadra_id}' non trovata")
            if squadra_obj.flg_attiva:
                return RisultatoOperazioneSquadra(ok=False, motivo="Squadra gia' attiva")

            squadra_obj.flg_attiva = True
            session.commit()
            return RisultatoOperazioneSquadra(ok=True, squadra_id=squadra_id)

    def elimina_squadra_definitivamente(self, squadra_id: str) -> RisultatoOperazioneSquadra:
        """Hard-delete, irreversibile: rimuove dal database la Squadra e le sue ComposizioneSquadra,
        indipendentemente dallo stato corrente. Rifiuta se una sua composizione, anche passata, e'
        mai stata legata a un Viaggio - lo storico viaggi/consegne (RF8) non va spezzato solo
        perche' la squadra che li ha effettuati viene rimossa (questo copre anche il caso di una
        composizione ancora attiva legata a un viaggio in corso, non solo lo storico)."""
        with self.session_factory() as session:
            squadra_obj = session.get(Squadra, squadra_id)
            if squadra_obj is None:
                return RisultatoOperazioneSquadra(ok=False, motivo=f"Squadra '{squadra_id}' non trovata")

            viaggio_storico = session.scalar(
                select(Viaggio.id)
                .join(ComposizioneSquadra, ComposizioneSquadra.id_composizione == Viaggio.composizione_id)
                .where(ComposizioneSquadra.squadra_id == squadra_id)
            )
            if viaggio_storico is not None:
                return RisultatoOperazioneSquadra(
                    ok=False,
                    squadra_id=squadra_id,
                    motivo="Impossibile eliminare definitivamente: la squadra ha viaggi nello storico",
                )

            composizioni = session.scalars(
                select(ComposizioneSquadra).where(ComposizioneSquadra.squadra_id == squadra_id)
            ).all()
            for composizione in composizioni:
                session.delete(composizione)
            session.delete(squadra_obj)

            session.commit()
            return RisultatoOperazioneSquadra(ok=True, squadra_id=squadra_id)

    def prossimo_id_squadra(self) -> str:
        """Prossimo id numerico libero per una nuova squadra: max(id esistenti) + 1 su TUTTE le
        squadre (attive e non), cosi' non collide mai con una gia' presente a DB anche se non piu'
        visibile in lista di default - a differenza di un semplice conteggio (che si sarebbe potuto
        ripetere dopo un'eliminazione)."""
        with self.session_factory() as session:
            ids_numerici = [
                int(id_) for id_ in session.scalars(select(Squadra.id)).all() if id_.isdigit()
            ]
        return str(max(ids_numerici, default=0) + 1)
