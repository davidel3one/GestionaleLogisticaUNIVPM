"""Pagina Viaggi: PageHeader + Filter Card + Table + Modal dettaglio/modifica (fonte: mockup
Sketch, artboard "Viaggi" + pattern del modale dettaglio di Squadre, stesso "titolo + sottotitolo
+ tabella", riusato qui con titolo "Viaggio {id}").

Il dettaglio READ-ONLY (dipendenti assegnati + ordini caricati) si apre cliccando l'ID del
viaggio (colonna LINK) - non piu' il precedente modale "Modifica date": non esiste un artboard
"Viaggi — Modifica (modale)" ne' un'operazione di modifica viaggio nelle RF (divergenza gia'
dichiarata in precedenza), e su richiesta esplicita dell'utente il click sull'ID ora apre il
dettaglio invece. Puramente di sola lettura: nessun bottone "Modifica" al suo interno (rimosso su
richiesta esplicita dell'utente - un'unica azione, non due entry point equivalenti).

**Modifica (partenza/arrivo/squadra/ordini)**: su richiesta esplicita dell'utente, l'UNICO
entry point e' la matita in Azioni (`_modifica_riga`) - solo per viaggi In
composizione/Pianificato (STATI_MODIFICABILI) apre direttamente `_apri_modale_modifica` invece di
limitarsi a cambiare stato; per gli altri stati resta il comportamento del redesign precedente
(annulla/ripristina, vedi componenti-gui.md) - `Table`/`ColumnDef` restano invariati, e' solo la
callback della RowAction a diramarsi in base allo stato della riga.

Il modale di modifica ha le due date, la squadra (GestoreLogistica.modifica_squadra_viaggio,
nuovo: prima la composizione era scrivibile solo alla creazione) e gli ordini gia' caricati.
L'aggiunta di ordini (bottone "+", icona `circle-plus` come le altre azioni, che diventa
`circle-check-big` verde non appena l'ordine e' stato agganciato) resta disponibile solo per
viaggi In composizione, stesso vincolo hard gia' presente in
GestoreLogistica.aggiungi_ordine_a_viaggio - qui la sezione viene semplicemente nascosta per
Pianificato, senza aggirare quel vincolo."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from gestionale_logistica.database.enums import StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import Camion, ComposizioneSquadra, Squadra, Viaggio
from gestionale_logistica.gui.components import (
    MINIMAL_SCROLLBAR_QSS,
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    DatePicker,
    EmptyState,
    LinkButton,
    Modal,
    PageHeader,
    RowAction,
    SearchField,
    Select,
    Table,
    TextEmphasis,
    load_lucide_icon,
)
from gestionale_logistica.gui.pages._form_layout import riga_2_colonne
from gestionale_logistica.logistica.gestore_logistica import (
    FILTRO_TUTTI,
    STATO_ORDINE_LABELS,
    STATO_VIAGGIO_LABELS,
    GestoreLogistica,
)

PAGE_SIZE = 12

# Stati per cui il bottone "Modifica" compare nel modale Dettaglio (decisione esplicita
# dell'utente): un viaggio In corso/Completato/Annullato resta visualizzabile ma non piu' modificabile.
STATI_MODIFICABILI = {
    STATO_VIAGGIO_LABELS[StatoViaggio.IN_COMPOSIZIONE],
    STATO_VIAGGIO_LABELS[StatoViaggio.PIANIFICATO],
}

STATO_BADGE_COLORS = {
    STATO_VIAGGIO_LABELS[StatoViaggio.IN_CORSO]: ("#FEF3C7", "#B45309"),
    STATO_VIAGGIO_LABELS[StatoViaggio.COMPLETATO]: ("#DFF5E5", "#1E8E3E"),
    STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO]: ("#FBE4E1", "#C0392B"),
    # "Pianificato" e "In composizione" non hanno bisogno di un override: coincidono gia'
    # esattamente con la palette di default di Table (Pianificato -> blu, In composizione ->
    # grigio neutro di fallback) - verificato pixel per pixel dal mockup, non un'assunzione.
}

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15


def _qdate_a_datetime(valore: QDate) -> datetime:
    data = valore.toPython()
    return datetime(data.year, data.month, data.day)


def _datetime_a_qdate(valore: datetime) -> QDate:
    return QDate(valore.year, valore.month, valore.day)


class ViaggiPage(QWidget):
    def __init__(self, gestore: GestoreLogistica, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gestore = gestore
        self._pagina_corrente = 1
        self._decrescente = False
        self._ordina_per = "data_partenza_prevista"
        self._filtro_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        self._costruisci_header(layout)
        self._costruisci_filtri(layout)
        self._costruisci_tabella(layout)

        self._reload()

    # --- costruzione UI -------------------------------------------------------------

    def _costruisci_header(self, layout: QVBoxLayout) -> None:
        # "Nuova pianificazione" lancia il wizard di pianificazione, non ancora costruito (per
        # decisione esplicita: prima la lista Viaggi, poi il wizard a parte). Visibile ma
        # disabilitato per ora, stesso trattamento gia' deciso per la tab "Esiti" in Ordini.
        bottone_pianificazione = Button(
            ButtonVariant.SECONDARY_HEADER_ADD,
            "Nuova pianificazione",
            load_lucide_icon("calendar-plus", "#2E2E2E", 13),
        )
        bottone_pianificazione.setEnabled(False)
        layout.addWidget(PageHeader("Viaggi", [bottone_pianificazione]))

    def _costruisci_filtri(self, layout: QVBoxLayout) -> None:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca ID viaggio, squadra...")
        self._select_stato = Select(
            "Stato", options=list(STATO_VIAGGIO_LABELS.values()), placeholder="Tutti"
        )
        self._campo_data = DatePicker("Data")
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._campo_data)
        riga.addStretch(1)

        self._etichetta_conteggio = QLabel()
        self._etichetta_conteggio.setStyleSheet("color: #5A6372;")
        riga.addWidget(self._etichetta_conteggio)

        link_ripristina = LinkButton("Ripristina filtri")
        link_ripristina.clicked.connect(self._ripristina_filtri)
        riga.addWidget(link_ripristina)

        card.content_layout.addLayout(riga)
        layout.addWidget(card)

        self._campo_ricerca.searchChanged.connect(self._on_filtro_cambiato)
        self._select_stato.valueChanged.connect(self._on_filtro_cambiato)
        self._campo_data.valueChanged.connect(self._on_data_filtro_cambiata)

    def _costruisci_tabella(self, layout: QVBoxLayout) -> None:
        self._tabella = Table(
            [
                ColumnDef(
                    key="id", label="ID", column_type=ColumnType.LINK, stretch=1,
                    on_click=self._apri_modale_dettaglio,
                ),
                ColumnDef(key="squadra", label="Squadra", column_type=ColumnType.LINK, stretch=1),
                ColumnDef(
                    key="n_ordini", label="N. ordini", emphasis=TextEmphasis.SECONDARY, stretch=1
                ),
                ColumnDef(key="partenza", label="Partenza", sortable=True, stretch=1),
                ColumnDef(key="arrivo", label="Arrivo", sortable=True, stretch=1),
                ColumnDef(
                    key="stato",
                    label="Stato",
                    column_type=ColumnType.STATUS_BADGE,
                    status_colors=STATO_BADGE_COLORS,
                    stretch=1,
                ),
                ColumnDef(
                    key="azioni",
                    label="Azioni",
                    column_type=ColumnType.ACTIONS,
                    width=76,
                    actions=[
                        RowAction("pencil", self._modifica_riga, tooltip="Modifica"),
                        RowAction("trash-2", self._elimina_riga),
                    ],
                ),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella)

    # --- dati -------------------------------------------------------------

    def _reload(self) -> None:
        pagina = self._gestore.visualizza_viaggi(
            ricerca=self._campo_ricerca.value() or None,
            filtro_stato=self._select_stato.value() or FILTRO_TUTTI,
            filtro_data=self._filtro_data,
            pagina=self._pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._decrescente,
            ordina_per=self._ordina_per,
        )
        righe = [
            {
                "id": r.id,
                "squadra": f"{r.squadra_id}",
                "n_ordini": f"{r.n_ordini} ordini",
                "partenza": r.data_partenza_prevista.strftime("%d/%m %H:%M"),
                "arrivo": r.data_arrivo_prevista.strftime("%d/%m %H:%M"),
                "stato": r.stato,
            }
            for r in pagina.viaggi
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} viaggi")

    # --- gestori eventi -------------------------------------------------------------

    def _on_filtro_cambiato(self, *_args) -> None:
        self._pagina_corrente = 1
        self._reload()

    def _on_data_filtro_cambiata(self, valore: QDate) -> None:
        self._filtro_data = valore.toPython()
        self._on_filtro_cambiato()

    def _on_sort_richiesto(self, colonna: str, ascending: bool) -> None:
        self._ordina_per = "data_arrivo_prevista" if colonna == "arrivo" else "data_partenza_prevista"
        self._decrescente = not ascending
        self._reload()

    def _on_pagina_richiesta(self, pagina: int) -> None:
        self._pagina_corrente = pagina
        self._reload()

    def _ripristina_filtri(self) -> None:
        self._campo_ricerca.set_value("")
        self._select_stato.set_value(None)
        self._campo_data.set_value(QDate.currentDate())
        self._filtro_data = None
        self._pagina_corrente = 1
        self._reload()

    def _modifica_riga(self, riga: dict) -> None:
        # Su richiesta esplicita dell'utente, la matita per un viaggio In composizione/Pianificato
        # apre direttamente il modale di modifica (ordini/partenza/squadra) invece di limitarsi a
        # cambiare stato - stesso modale gia' raggiungibile anche da ID -> Dettaglio -> "Modifica".
        # Per gli altri stati resta il comportamento di prima: da Annullato ripristina, altrimenti
        # annulla (annulla_viaggio rifiuta comunque da solo se gia' Completato).
        if riga["stato"] in STATI_MODIFICABILI:
            self._apri_modale_modifica(riga)
            return
        if riga["stato"] == STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO]:
            risultato = self._gestore.ripristina_viaggio(riga["id"])
            titolo_errore = "Impossibile ripristinare"
        else:
            risultato = self._gestore.annulla_viaggio(riga["id"])
            titolo_errore = "Impossibile annullare"
        if not risultato.ok:
            QMessageBox.warning(self, titolo_errore, risultato.motivo or "Operazione rifiutata.")
        self._reload()

    def _elimina_riga(self, riga: dict) -> None:
        # Soft-delete (stesso comportamento di annulla_viaggio sul pulsante modifica quando la
        # riga non e' gia' terminale) - non elimina i dati, preserva lo storico (RF8).
        risultato = self._gestore.annulla_viaggio(riga["id"])
        if not risultato.ok:
            QMessageBox.warning(self, "Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    # --- modali -------------------------------------------------------------

    def _apri_modale_dettaglio(self, riga: dict) -> None:
        dettaglio = self._gestore.dettaglio_viaggio(riga["id"])
        if dettaglio is None:
            QMessageBox.warning(self, "Viaggio non trovato", "Il viaggio non esiste più.")
            self._reload()
            return

        sottotitolo_parti = [", ".join(dettaglio.dipendenti) or "—", dettaglio.stato]

        # Sola lettura: la modifica (ordini/partenza/squadra) si apre solo dalla matita in Azioni
        # (_modifica_riga), su richiesta esplicita dell'utente - niente bottone "Modifica" qui.
        modale = Modal(
            f"Viaggio {dettaglio.id}", subtitle=" · ".join(sottotitolo_parti), width=900
        )

        if not dettaglio.ordini:
            modale.add_widget(
                EmptyState("Nessun ordine caricato", "Gli ordini agganciati a questo viaggio appariranno qui")
            )
        else:
            tabella_ordini = Table(
                [
                    ColumnDef(key="id", label="ID", column_type=ColumnType.LINK, stretch=1),
                    ColumnDef(key="cliente", label="Cliente", stretch=1),
                    ColumnDef(
                        key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=2
                    ),
                ]
            )
            righe_ordini = [
                {"id": o.id, "cliente": o.cliente, "indirizzo": o.indirizzo} for o in dettaglio.ordini
            ]
            tabella_ordini.set_rows(righe_ordini)
            tabella_ordini.set_pagination(1, len(righe_ordini), max(len(righe_ordini), 1))
            modale.add_widget(tabella_ordini)

        modale.show_over(self)

    def _opzioni_squadre(self) -> dict[str, str]:
        """Mappa 'squadra_id (targa)' -> id della composizione attiva di quella squadra, per
        popolare la Select 'Squadra' del modale Modifica - stesso pattern di
        SquadrePage._opzioni_camion/_opzioni_dipendenti (query diretta invece di un metodo
        dedicato in GestoreLogistica, che non ha altrimenti bisogno di conoscere Squadra). Solo
        squadre attive con una composizione attiva: modifica_squadra_viaggio richiede sempre un
        camion e due dipendenti agganciati, stesso vincolo di apri_composizione in GestoreSquadre."""
        with self._gestore.session_factory() as session:
            righe = session.execute(
                select(ComposizioneSquadra.squadra_id, ComposizioneSquadra.id_composizione, Camion.targa)
                .join(Squadra, Squadra.id == ComposizioneSquadra.squadra_id)
                .join(Camion, Camion.id == ComposizioneSquadra.camion_id)
                .where(ComposizioneSquadra.flg_attiva.is_(True), Squadra.flg_attiva.is_(True))
            ).all()
        return {f"{squadra_id} ({targa})": composizione_id for squadra_id, composizione_id, targa in righe}

    def _apri_modale_modifica(self, riga: dict) -> None:
        with self._gestore.session_factory() as session:
            viaggio_obj = session.get(Viaggio, riga["id"])
        if viaggio_obj is None:
            QMessageBox.warning(self, "Viaggio non trovato", "Il viaggio non esiste più.")
            self._reload()
            return

        viaggio_id = riga["id"]
        # RF11/aggiungi_ordine_a_viaggio ammette solo viaggi In composizione: la sezione "Aggiungi
        # ordini" va quindi nascosta (non solo disabilitata) per Pianificato, invece di mostrare un
        # bottone che fallirebbe sempre.
        modificabile_ordini = viaggio_obj.stato_viaggio == StatoViaggio.IN_COMPOSIZIONE

        opzioni_squadre = self._opzioni_squadre()
        etichetta_squadra_corrente = next(
            (
                etichetta
                for etichetta, comp_id in opzioni_squadre.items()
                if comp_id == viaggio_obj.composizione_id
            ),
            None,
        )

        campo_partenza = DatePicker("Data partenza prevista")
        campo_partenza.set_value(_datetime_a_qdate(viaggio_obj.data_partenza_prevista))
        campo_arrivo = DatePicker("Data arrivo prevista")
        campo_arrivo.set_value(_datetime_a_qdate(viaggio_obj.data_arrivo_prevista))

        campo_squadra = Select("Squadra", options=list(opzioni_squadre), placeholder="Seleziona squadra")
        if etichetta_squadra_corrente is not None:
            campo_squadra.set_value(etichetta_squadra_corrente)

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Salva")
        modale = Modal(
            f"Modifica viaggio {viaggio_id}", width=640, footer_buttons=[bottone_annulla, bottone_conferma]
        )
        modale.content_layout.addLayout(riga_2_colonne(campo_partenza, campo_arrivo))
        modale.add_widget(campo_squadra)

        etichetta_ordini = QLabel("Ordini nel viaggio")
        etichetta_ordini.setStyleSheet("color: #8A93A0; margin-top: 8px;")
        modale.add_widget(etichetta_ordini)

        ordini_viaggio_container = QWidget()
        ordini_viaggio_layout = QVBoxLayout(ordini_viaggio_container)
        ordini_viaggio_layout.setContentsMargins(0, 0, 0, 0)
        ordini_viaggio_layout.setSpacing(0)
        modale.add_widget(ordini_viaggio_container)

        def _aggiorna_ordini_nel_viaggio() -> None:
            while ordini_viaggio_layout.count():
                item = ordini_viaggio_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            dettaglio = self._gestore.dettaglio_viaggio(viaggio_id)
            ordini_correnti = dettaglio.ordini if dettaglio is not None else []
            if not ordini_correnti:
                ordini_viaggio_layout.addWidget(
                    EmptyState("Nessun ordine caricato", "Gli ordini aggiunti a questo viaggio appariranno qui")
                )
                return
            tabella = Table(
                [
                    ColumnDef(key="id", label="ID ordine", stretch=1),
                    ColumnDef(key="cliente", label="Cliente", stretch=1),
                    ColumnDef(
                        key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=2
                    ),
                ],
                show_footer=False,
            )
            tabella.set_rows(
                [{"id": o.id, "cliente": o.cliente, "indirizzo": o.indirizzo} for o in ordini_correnti]
            )
            ordini_viaggio_layout.addWidget(tabella)

        _aggiorna_ordini_nel_viaggio()

        if modificabile_ordini:
            etichetta_aggiungi = QLabel("Aggiungi ordini")
            etichetta_aggiungi.setStyleSheet("color: #8A93A0; margin-top: 8px;")
            modale.add_widget(etichetta_aggiungi)

            campo_ricerca_ordini = SearchField(placeholder="Cerca ordine da aggiungere...")
            modale.add_widget(campo_ricerca_ordini)

            candidati_attuali: list[dict] = []

            def _righe_candidati(testo: str) -> list[dict]:
                pagina = self._gestore.visualizza_ordini(
                    ricerca=testo or None,
                    filtro_stato=STATO_ORDINE_LABELS[StatoOrdine.RICEVUTO],
                    dimensione_pagina=0,
                )
                return [
                    {"id": o.id, "cliente": o.cliente, "indirizzo": o.indirizzo, "aggiunto": False}
                    for o in pagina.ordini
                ]

            def _aggiungi_ordine(riga_candidato: dict) -> None:
                esito = self._gestore.aggiungi_ordine_a_viaggio(viaggio_id, riga_candidato["id"])
                if not esito.ammesso:
                    QMessageBox.warning(
                        self, "Impossibile aggiungere", esito.motivo or "Operazione rifiutata."
                    )
                    return
                # Aggiorna solo il flag della riga gia' visualizzata (niente nuova query): appena
                # agganciato l'ordine non e' piu' "Da pianificare", quindi una nuova query lo
                # escluderebbe e lo farebbe sparire invece di mostrare la spunta verde di conferma
                # richiesta - resta al suo posto finche' non parte una nuova ricerca.
                for riga_visualizzata in candidati_attuali:
                    if riga_visualizzata["id"] == riga_candidato["id"]:
                        riga_visualizzata["aggiunto"] = True
                tabella_candidati.set_rows(candidati_attuali)
                _aggiorna_ordini_nel_viaggio()

            def _ricarica_candidati(testo: str = "") -> None:
                nonlocal candidati_attuali
                candidati_attuali = _righe_candidati(testo)
                tabella_candidati.set_rows(candidati_attuali)

            tabella_candidati = Table(
                [
                    ColumnDef(key="id", label="ID ordine", stretch=1),
                    ColumnDef(key="cliente", label="Cliente", emphasis=TextEmphasis.SECONDARY, stretch=1),
                    ColumnDef(
                        key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=2
                    ),
                    ColumnDef(
                        key="azioni",
                        label="",
                        column_type=ColumnType.ACTIONS,
                        width=44,
                        actions=[
                            RowAction(
                                "circle-plus",
                                _aggiungi_ordine,
                                tooltip="Aggiungi al viaggio",
                                predicate=lambda r: not r["aggiunto"],
                            ),
                            RowAction(
                                "circle-check-big",
                                lambda r: None,
                                color="#1E8E3E",
                                tooltip="Aggiunto",
                                predicate=lambda r: r["aggiunto"],
                            ),
                        ],
                    ),
                ],
                show_footer=False,
            )

            campo_ricerca_ordini.searchChanged.connect(_ricarica_candidati)
            _ricarica_candidati()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(220)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet(
                f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}"
            )
            scroll.setWidget(tabella_candidati)
            modale.add_widget(scroll)

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            risultato = self._gestore.modifica_date_viaggio(
                viaggio_id,
                data_partenza_prevista=_qdate_a_datetime(campo_partenza.value()),
                data_arrivo_prevista=_qdate_a_datetime(campo_arrivo.value()),
            )
            if not risultato.ok:
                QMessageBox.warning(self, "Impossibile salvare", risultato.motivo or "Operazione rifiutata.")
                return

            nuova_composizione_id = opzioni_squadre.get(campo_squadra.value())
            if nuova_composizione_id is not None and nuova_composizione_id != viaggio_obj.composizione_id:
                risultato_squadra = self._gestore.modifica_squadra_viaggio(viaggio_id, nuova_composizione_id)
                if not risultato_squadra.ok:
                    QMessageBox.warning(
                        self, "Impossibile salvare", risultato_squadra.motivo or "Operazione rifiutata."
                    )
                    return

            modale.close()
            self._reload()

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)
