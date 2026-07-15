import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import ComposizioneSquadra, Dipendente, Viaggio

dipendente = CRUDBase[Dipendente](Dipendente)

# Formato standard del codice fiscale italiano (16 caratteri): 6 lettere (cognome+nome) + 2 cifre
# (anno) + 1 lettera (mese) + 2 cifre (giorno+sesso) + 1 lettera + 3 cifre (comune) + 1 lettera
# (carattere di controllo). Solo controllo di formato, non il calcolo del carattere di controllo
# (fuori scope: servirebbe la tabella di conversione ufficiale, non solo una regex).
CODICE_FISCALE_REGEX = re.compile(r"^[A-Za-z]{6}[0-9]{2}[ABCDEHLMPRSTabcdehlmprst][0-9]{2}[A-Za-z][0-9]{3}[A-Za-z]$")

# Stati derivati esposti da visualizza_dipendenti (usati anche come valori del filtro stato) -
# stesso principio di STATO_ATTIVA/STATO_IN_VIAGGIO/STATO_NON_ATTIVA in gestore_squadre.py.
STATO_ATTIVO = "Attivo"
STATO_IN_VIAGGIO = "In viaggio"
STATO_CESSATO = "Cessato"
FILTRO_TUTTI = "Tutti"

# Segnaposto usato quando un dipendente non ha una composizione attiva da cui ricavare la squadra.
SEGNAPOSTO_SQUADRA = "—"


@dataclass
class RisultatoOperazioneDipendente:
    ok: bool
    dipendente_id: str | None = None
    motivo: str | None = None


@dataclass
class DipendenteVista:
    id: str
    nome: str
    cognome: str
    codice_fiscale: str
    squadra_corrente: str
    data_assunzione: datetime
    flg_certificazione_gas: bool
    stato: str


@dataclass
class PaginaDipendenti:
    """Pagina di risultati di visualizza_dipendenti: solo la fetta richiesta + il totale filtrato."""

    dipendenti: list[DipendenteVista]
    totale: int


def _stato_derivato(flg_attivo: bool, in_viaggio: bool) -> str:
    """Stato mostrato in lista: Cessato > In viaggio (solo IN_CORSO) > Attivo."""
    if not flg_attivo:
        return STATO_CESSATO
    if in_viaggio:
        return STATO_IN_VIAGGIO
    return STATO_ATTIVO


def _squadra_per_dipendente(session) -> dict[str, str]:
    """Mappa dipendente_id -> "Squadra <squadra_id>" dalla composizione attiva piu' recente in cui
    il dipendente compare come dipendente_1 o dipendente_2. Lookup inverso di
    gestore_squadre._select_composizioni_attive() (li' squadra->membri, qui dipendente->squadra):
    una sola query per tutti i dipendenti, niente N+1."""
    piu_recente: dict[str, tuple[datetime, str, str]] = {}
    righe = session.execute(
        select(
            ComposizioneSquadra.dipendente_1_id,
            ComposizioneSquadra.dipendente_2_id,
            ComposizioneSquadra.squadra_id,
            ComposizioneSquadra.data_inizio_validita,
            ComposizioneSquadra.id_composizione,
        ).where(ComposizioneSquadra.flg_attiva.is_(True))
    ).all()
    for dipendente_1_id, dipendente_2_id, squadra_id, data_inizio, id_composizione in righe:
        for dipendente_id in (dipendente_1_id, dipendente_2_id):
            corrente = piu_recente.get(dipendente_id)
            chiave = (data_inizio, id_composizione)
            if corrente is None or chiave > (corrente[0], corrente[1]):
                piu_recente[dipendente_id] = (data_inizio, id_composizione, squadra_id)
    return {dip_id: f"Squadra {dati[2]}" for dip_id, dati in piu_recente.items()}


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
        """RF1: registra un nuovo dipendente. Rifiuta codice fiscale mal formato, o id/codice_fiscale
        gia' in uso (Fix 7)."""
        if not CODICE_FISCALE_REGEX.match(codice_fiscale):
            return RisultatoOperazioneDipendente(
                ok=False, motivo=f"Codice fiscale '{codice_fiscale}' non valido"
            )
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

    def visualizza_dipendenti(
        self,
        ricerca: str | None = None,
        filtro_squadra: str | None = None,
        filtro_stato: str = FILTRO_TUTTI,
        pagina: int = 1,
        dimensione_pagina: int = 20,
        decrescente: bool = False,
    ) -> PaginaDipendenti:
        """Elenco filtrato/ordinato/paginato dei dipendenti. Filtri: ricerca testuale (nome/
        cognome/codice fiscale), filtro stato (Tutti/Attivo/In viaggio/Cessato), filtro squadra
        corrente, ordinamento per data_assunzione, paginazione lato Python. Stesso pattern di
        GestoreSquadre.visualizza_squadre: stato "In viaggio" derivato con query aggregate sui
        Viaggio IN_CORSO (niente N+1), squadra corrente con una sola query sulle composizioni
        attive."""
        with self.session_factory() as session:
            # Insieme dei dipendenti "in viaggio": composizione ATTIVA legata a un Viaggio
            # IN_CORSO. ComposizioneSquadra ha due FK verso Dipendente (dipendente_1_id/
            # dipendente_2_id, a differenza della FK singola squadra_id di GestoreSquadre), quindi
            # servono due query invece di una, unite in Python - stesso principio "una query per
            # concetto aggregato, non per riga".
            filtro_in_corso = (
                ComposizioneSquadra.flg_attiva.is_(True),
                Viaggio.stato_viaggio == StatoViaggio.IN_CORSO,
            )
            in_viaggio_ids = set(
                session.scalars(
                    select(ComposizioneSquadra.dipendente_1_id)
                    .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
                    .where(*filtro_in_corso)
                ).all()
            ) | set(
                session.scalars(
                    select(ComposizioneSquadra.dipendente_2_id)
                    .join(Viaggio, Viaggio.composizione_id == ComposizioneSquadra.id_composizione)
                    .where(*filtro_in_corso)
                ).all()
            )

            squadra_per_dipendente = _squadra_per_dipendente(session)

            ordine = Dipendente.data_assunzione.desc() if decrescente else Dipendente.data_assunzione.asc()
            dipendenti = session.scalars(select(Dipendente).order_by(ordine)).all()

            righe: list[DipendenteVista] = []
            for dip in dipendenti:
                stato = _stato_derivato(dip.flg_attivo, dip.id in in_viaggio_ids)
                righe.append(
                    DipendenteVista(
                        id=dip.id,
                        nome=dip.nome,
                        cognome=dip.cognome,
                        codice_fiscale=dip.codice_fiscale,
                        squadra_corrente=squadra_per_dipendente.get(dip.id, SEGNAPOSTO_SQUADRA),
                        data_assunzione=dip.data_assunzione,
                        flg_certificazione_gas=dip.flg_certificazione_gas,
                        stato=stato,
                    )
                )

            if filtro_stato and filtro_stato != FILTRO_TUTTI:
                righe = [r for r in righe if r.stato == filtro_stato]

            if filtro_squadra:
                righe = [r for r in righe if r.squadra_corrente == filtro_squadra]

            if ricerca:
                termine = ricerca.strip().lower()
                if termine:
                    righe = [
                        r
                        for r in righe
                        if termine in r.nome.lower()
                        or termine in r.cognome.lower()
                        or termine in r.codice_fiscale.lower()
                    ]

            totale = len(righe)
            if dimensione_pagina > 0:
                inizio = max(pagina - 1, 0) * dimensione_pagina
                righe = righe[inizio : inizio + dimensione_pagina]

            return PaginaDipendenti(dipendenti=righe, totale=totale)

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
        potrebbe mai chiudere (richiede almeno un ordine) - uno stato "zombie" indefinito.

        La cascata da sola non basta per un Viaggio IN_COMPOSIZIONE aperto *prima* del
        licenziamento: aggiungi_ordine_a_viaggio() controlla solo viaggio.stato_viaggio, mai
        composizione.flg_attiva, quindi quel viaggio diventerebbe comunque uno zombie bloccato.
        Percio' il licenziamento viene rifiutato a monte se il dipendente e' coinvolto in un
        Viaggio IN_COMPOSIZIONE o IN_CORSO - piu' semplice e sicuro che introdurre un annullamento
        esplicito (StatoViaggio.ANNULLATO e' definito ma non ancora usato da nessuna operazione)."""
        with self.session_factory() as session:
            dip = session.get(Dipendente, id_)
            if dip is None:
                return RisultatoOperazioneDipendente(ok=False, motivo=f"Dipendente '{id_}' non trovato")
            if not dip.flg_attivo:
                return RisultatoOperazioneDipendente(ok=False, motivo="Dipendente gia' licenziato")

            composizioni = session.scalars(
                select(ComposizioneSquadra).where(
                    or_(
                        ComposizioneSquadra.dipendente_1_id == id_,
                        ComposizioneSquadra.dipendente_2_id == id_,
                    )
                )
            ).all()
            if composizioni:
                viaggio_bloccante = session.scalar(
                    select(Viaggio.id).where(
                        Viaggio.composizione_id.in_([c.id_composizione for c in composizioni]),
                        Viaggio.stato_viaggio.in_([StatoViaggio.IN_COMPOSIZIONE, StatoViaggio.IN_CORSO]),
                    )
                )
                if viaggio_bloccante is not None:
                    return RisultatoOperazioneDipendente(
                        ok=False,
                        motivo=(
                            f"Impossibile licenziare: coinvolto nel viaggio '{viaggio_bloccante}', "
                            "ancora in composizione o in corso"
                        ),
                    )

            dip.flg_attivo = False
            dip.data_licenziamento = data_licenziamento or datetime.now()

            for composizione in composizioni:
                if composizione.flg_attiva:
                    composizione.flg_attiva = False

            session.commit()
            return RisultatoOperazioneDipendente(ok=True, dipendente_id=id_)

    def riassumi_dipendente(self, id_: str) -> RisultatoOperazioneDipendente:
        """Annulla un licenziamento fatto per errore: rimette flg_attivo=True e azzera
        data_licenziamento. Non riattiva le ComposizioneSquadra disattivate dal licenziamento
        (andrebbe rifatta l'assegnazione a una squadra esplicitamente, stessa logica di
        un'assunzione nuova - non si presume quale squadra fosse quella giusta)."""
        with self.session_factory() as session:
            dip = session.get(Dipendente, id_)
            if dip is None:
                return RisultatoOperazioneDipendente(ok=False, motivo=f"Dipendente '{id_}' non trovato")
            if dip.flg_attivo:
                return RisultatoOperazioneDipendente(ok=False, motivo="Dipendente gia' attivo")

            dip.flg_attivo = True
            dip.data_licenziamento = None

            session.commit()
            return RisultatoOperazioneDipendente(ok=True, dipendente_id=id_)
