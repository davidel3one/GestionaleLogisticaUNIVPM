"""Pagina Ordini: TabBar (Ordini/Esiti) + PageHeader + Filter Card + Table (fonte: mockup Sketch,
artboard "Ordini" / "Esiti").

- Tab "Ordini": lista/filtri/tabella. Colonna Azioni: "elimina" (hard-delete,
  elimina_ordine_definitivamente) sempre presente; "Registra esito" (matita, RF16-RF18) visibile
  solo sulle righe con un ordine su un viaggio attualmente IN_CORSO senza gia' un esito per quel
  viaggio (`OrdineVista.puo_registrare_esito`, calcolato lato backend - stessa condizione
  verificata in modo autoritativo da GestoreRendicontazione.registra_esito()).
- Tab "Esiti": storico degli EsitoConsegna gia' registrati (GestoreRendicontazione.elenca_esiti()).
  Colonna Azioni: "modifica" (matita su Completato, occhio su Fallito - stessa RegistraEsitoModal
  in modalita' modifica, GestoreRendicontazione.modifica_esito()) ed "elimina" (cestino, sempre,
  GestoreRendicontazione.elimina_esito()).
- Colonna "colli" omessa: nessun campo corrispondente nel modello Ordine, il mockup la mostra ma
  non corrisponde a nulla di reale.
"""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    ConfirmModal,
    DateFilterField,
    ImportCsvModal,
    LinkButton,
    MultiSelect,
    PageHeader,
    RowAction,
    SearchField,
    TabBar,
    Table,
    TextEmphasis,
    ToastManager,
    load_lucide_icon,
)
from gestionale_logistica.gui.pages.ordini._registra_esito_modal import RegistraEsitoModal
from gestionale_logistica.logistica.gestore_logistica import (
    STATO_ORDINE_LABELS,
    GestoreLogistica,
    StatoOrdine,
)
from gestionale_logistica.rendicontazione.gestore_rendicontazione import GestoreRendicontazione

PAGE_SIZE = 20

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15

ESITO_STATUS_COLORS = {"Completato": ("#DFF5E5", "#1E8E3E")}


def _formatta_numero(valore: float) -> str:
    return str(int(valore)) if valore == int(valore) else str(valore)


def _formatta_peso_volume(peso: float, volume_cargo: float) -> str:
    return f"{_formatta_numero(peso)} kg · {_formatta_numero(volume_cargo)} m³"


class OrdiniPage(QWidget):
    def __init__(
        self,
        gestore: GestoreLogistica,
        gestore_rendicontazione: GestoreRendicontazione | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._gestore = gestore
        self._gestore_rendicontazione = gestore_rendicontazione or GestoreRendicontazione()
        self._pagina_corrente = 1
        self._decrescente = False
        self._filtro_data = None
        self._esiti_pagina_corrente = 1
        self._esiti_filtro_data = None
        self._esiti_decrescente = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        self._costruisci_header(layout)
        self._costruisci_tab_bar(layout)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._costruisci_vista_ordini())
        self._stack.addWidget(self._costruisci_vista_esiti())
        layout.addWidget(self._stack)

        self._toasts = ToastManager(self)

        self._reload()

    # --- costruzione UI -------------------------------------------------------------

    def _costruisci_tab_bar(self, layout: QVBoxLayout) -> None:
        tab_bar = TabBar(["Ordini", "Esiti"])
        tab_bar.currentChanged.connect(self._on_tab_cambiata)
        layout.addWidget(tab_bar)

    def _costruisci_header(self, layout: QVBoxLayout) -> None:
        bottone_importa = Button(
            ButtonVariant.SECONDARY_HEADER_ADD,
            "Importa CSV",
            load_lucide_icon("upload", "#2E2E2E", 15),
        )
        bottone_importa.clicked.connect(self._apri_import_csv)
        layout.addWidget(PageHeader("Ordini", [bottone_importa]))

    def _costruisci_vista_ordini(self) -> QWidget:
        vista = QWidget()
        layout = QVBoxLayout(vista)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)

        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca cliente, indirizzo, ID...")
        # Filtro a scelta multipla (2026-07-16, su richiesta esplicita dell'utente): vedi la stessa
        # nota in gui/pages/dipendenti/__init__.py.
        self._select_stato = MultiSelect(
            "Stato", options=list(STATO_ORDINE_LABELS.values()), placeholder="Tutti", compact=True
        )
        # Stesso pattern MultiSelect degli altri filtri: opzioni popolate dai valori distinti gia'
        # visti su Ordine.negozio_partner (stesso elenco gia' usato dal selettore "select o crea
        # nuovo" del modale Importa CSV, GestoreLogistica.elenco_negozi_partner()), piu' "Non
        # specificato" - lo stesso valore con cui visualizza_ordini rende gli ordini con
        # negozio_partner NULL (r.negozio_partner or "Non specificato"): senza questa opzione la
        # colonna mostrerebbe righe "Non specificato" impossibili da isolare con questo filtro
        # (elenco_negozi_partner esclude i NULL, essendo un DISTINCT sul campo reale).
        self._select_negozio_partner = MultiSelect(
            "Negozio partner",
            options=[*self._gestore.elenco_negozi_partner(), "Non specificato"],
            placeholder="Tutti",
            compact=True,
        )
        self._campo_data = DateFilterField()
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._select_negozio_partner)
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
        self._select_negozio_partner.valueChanged.connect(self._on_filtro_cambiato)
        self._campo_data.valueChanged.connect(self._on_data_filtro_cambiata)

        self._tabella = Table(
            [
                ColumnDef(key="id", label="ID", column_type=ColumnType.TEXT, stretch=1),
                ColumnDef(key="cliente", label="Cliente", stretch=1),
                ColumnDef(key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=2),
                ColumnDef(
                    key="negozio_partner",
                    label="Negozio partner",
                    emphasis=TextEmphasis.SECONDARY,
                    stretch=1,
                ),
                # Etichetta "Arrivo viaggio" invece del semplice "DATA" del mockup: il valore
                # viene da Viaggio.data_arrivo_prevista, non e' una data propria dell'ordine -
                # va reso inequivocabile nell'interfaccia (decisione dell'utente), non solo un
                # valore nudo indistinguibile da un'ipotetica data ordine.
                ColumnDef(key="arrivo_viaggio", label="Arrivo viaggio", sortable=True, stretch=1),
                ColumnDef(
                    key="peso_volume", label="Peso / Volume", emphasis=TextEmphasis.SECONDARY, stretch=1
                ),
                ColumnDef(key="stato", label="Stato", column_type=ColumnType.STATUS_BADGE, stretch=1),
                ColumnDef(
                    key="azioni",
                    label="Azioni",
                    column_type=ColumnType.ACTIONS,
                    width=48,
                    actions=[
                        RowAction(
                            "pencil",
                            self._registra_esito,
                            predicate=lambda riga: riga["puo_registrare_esito"],
                        ),
                        RowAction(
                            "trash-2",
                            self._elimina_riga,
                            predicate=lambda riga: riga["stato"]
                            != STATO_ORDINE_LABELS[StatoOrdine.IN_CONSEGNA],
                        ),
                    ],
                ),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella, 1)

        return vista

    def _costruisci_vista_esiti(self) -> QWidget:
        vista = QWidget()
        layout = QVBoxLayout(vista)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)

        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._esiti_campo_ricerca = SearchField(placeholder="Cerca cliente, causale, ID...")
        self._esiti_select_esito = MultiSelect(
            "Esito", options=["Completato", "Fallito"], placeholder="Tutti", compact=True
        )
        self._esiti_campo_data = DateFilterField()
        riga.addWidget(self._esiti_campo_ricerca, 1)
        riga.addWidget(self._esiti_select_esito)
        riga.addWidget(self._esiti_campo_data)
        riga.addStretch(1)

        self._esiti_etichetta_conteggio = QLabel()
        self._esiti_etichetta_conteggio.setStyleSheet("color: #5A6372;")
        riga.addWidget(self._esiti_etichetta_conteggio)

        link_ripristina = LinkButton("Ripristina filtri")
        link_ripristina.clicked.connect(self._esiti_ripristina_filtri)
        riga.addWidget(link_ripristina)

        card.content_layout.addLayout(riga)
        layout.addWidget(card)

        self._esiti_campo_ricerca.searchChanged.connect(self._on_esiti_filtro_cambiato)
        self._esiti_select_esito.valueChanged.connect(self._on_esiti_filtro_cambiato)
        self._esiti_campo_data.valueChanged.connect(self._on_esiti_data_filtro_cambiata)

        self._esiti_tabella = Table(
            [
                ColumnDef(key="id", label="ID", column_type=ColumnType.TEXT, stretch=1),
                ColumnDef(key="cliente", label="Cliente", stretch=1),
                ColumnDef(
                    key="esito",
                    label="Esito",
                    column_type=ColumnType.STATUS_BADGE,
                    status_colors=ESITO_STATUS_COLORS,
                    stretch=1,
                ),
                ColumnDef(key="causale", label="Causale", emphasis=TextEmphasis.SECONDARY, stretch=2),
                ColumnDef(key="data_registrazione", label="Data registrazione", sortable=True, stretch=1),
                ColumnDef(
                    key="azioni",
                    label="Azioni",
                    column_type=ColumnType.ACTIONS,
                    width=48,
                    actions=[
                        # Fallito: "occhio" invece di "matita" - la modifica su un esito Fallito
                        # comporta sempre rivedere causale + prove allegate (almeno una
                        # obbligatoria), quindi l'icona anticipa che si sta aprendo una revisione
                        # della documentazione, non un semplice cambio di stato come su Completato.
                        RowAction(
                            "pencil", self._modifica_esito, predicate=lambda riga: riga["esito"] == "Completato"
                        ),
                        RowAction(
                            "eye", self._modifica_esito, predicate=lambda riga: riga["esito"] == "Fallito"
                        ),
                        RowAction("trash-2", self._elimina_esito),
                    ],
                ),
            ]
        )
        self._esiti_tabella.sortRequested.connect(self._on_esiti_sort_richiesto)
        self._esiti_tabella.pageChanged.connect(self._on_esiti_pagina_richiesta)
        layout.addWidget(self._esiti_tabella, 1)

        return vista

    # --- dati -------------------------------------------------------------

    def _reload(self) -> None:
        pagina = self._gestore.visualizza_ordini(
            ricerca=self._campo_ricerca.value() or None,
            filtro_stato=self._select_stato.value(),
            filtro_negozio_partner=self._select_negozio_partner.value(),
            filtro_data=self._filtro_data,
            pagina=self._pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._decrescente,
        )
        righe = [
            {
                "id": r.id,
                "cliente": r.cliente,
                "indirizzo": r.indirizzo,
                "negozio_partner": r.negozio_partner,
                "arrivo_viaggio": r.data_arrivo_viaggio.strftime("%d/%m/%Y") if r.data_arrivo_viaggio else "—",
                "peso_volume": _formatta_peso_volume(r.peso, r.volume_cargo),
                "stato": r.stato,
                "puo_registrare_esito": r.puo_registrare_esito,
            }
            for r in pagina.ordini
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} ordini")

    def _reload_esiti(self) -> None:
        pagina = self._gestore_rendicontazione.elenca_esiti(
            ricerca=self._esiti_campo_ricerca.value() or None,
            filtro_esito=self._esiti_select_esito.value(),
            filtro_data=self._esiti_filtro_data,
            pagina=self._esiti_pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._esiti_decrescente,
        )
        righe = [
            {
                "id": r.ordine_id,
                "cliente": r.cliente,
                "indirizzo": r.indirizzo,
                "peso_volume": _formatta_peso_volume(r.peso, r.volume_cargo),
                "esito": r.esito,
                "causale_codice": r.causale_codice,
                "causale": r.causale or "—",
                "esito_id": r.id,
                "data_registrazione": r.data_registrazione.strftime("%d/%m/%Y"),
            }
            for r in pagina.esiti
        ]
        self._esiti_tabella.set_rows(righe)
        self._esiti_tabella.set_pagination(self._esiti_pagina_corrente, pagina.totale, PAGE_SIZE)
        self._esiti_etichetta_conteggio.setText(f"{pagina.totale} esiti")

    # --- gestori eventi: tab -------------------------------------------------------------

    def _on_tab_cambiata(self, indice: int) -> None:
        self._stack.setCurrentIndex(indice)
        if indice == 1:
            self._reload_esiti()
        else:
            self._reload()

    # --- gestori eventi: tab Ordini -------------------------------------------------------------

    def _on_filtro_cambiato(self, *_args) -> None:
        self._pagina_corrente = 1
        self._reload()

    def _on_data_filtro_cambiata(self, valore: QDate) -> None:
        self._filtro_data = valore.toPython()
        self._on_filtro_cambiato()

    def _on_sort_richiesto(self, colonna: str, ascending: bool) -> None:
        self._decrescente = not ascending
        self._reload()

    def _on_pagina_richiesta(self, pagina: int) -> None:
        self._pagina_corrente = pagina
        self._reload()

    def _ripristina_filtri(self) -> None:
        self._campo_ricerca.set_value("")
        self._select_stato.set_value([])
        self._select_negozio_partner.set_value([])
        self._campo_data.set_value(QDate.currentDate())
        self._filtro_data = None
        self._pagina_corrente = 1
        self._reload()

    def _apri_import_csv(self) -> None:
        # Riferimento tenuto su self: ImportCsvModal e' un QObject senza parent Qt esplicito,
        # una variabile locale verrebbe garbage-collected da Python prima che l'utente finisca
        # il flusso a 2 passi (stesso motivo/pattern di dashboard_page.py._apri_import_csv).
        self._import_modal = ImportCsvModal(self, self._gestore)
        self._import_modal.importCompleted.connect(lambda _: self._reload())
        self._import_modal.show()

    def _elimina_riga(self, riga: dict) -> None:
        # Conferma esplicita richiesta dall'utente prima di procedere (stesso pattern gia' usato
        # su Camion/Dipendenti): qui l'eliminazione e' definitiva (elimina_ordine_definitivamente,
        # hard-delete), non un soft-delete come per le altre pagine - messaggio diverso di conseguenza.
        modale = ConfirmModal(
            "Elimina ordine",
            f"Sei sicuro di voler eliminare l'ordine {riga['id']} ({riga['cliente']})? "
            "L'eliminazione è definitiva e non è reversibile.",
        )
        modale.confirmed.connect(lambda: self._conferma_elimina_riga(riga))
        modale.show_over(self)

    def _conferma_elimina_riga(self, riga: dict) -> None:
        risultato = self._gestore.elimina_ordine_definitivamente(riga["id"])
        if not risultato.ok:
            self._toasts.show_error("Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    def _registra_esito(self, riga: dict) -> None:
        # Riferimento tenuto su self, stesso motivo di _import_modal sopra.
        self._esito_modal = RegistraEsitoModal(riga, self._gestore_rendicontazione)
        self._esito_modal.esitoRegistrato.connect(self._on_esito_registrato)
        self._esito_modal.show_over(self)

    def _on_esito_registrato(self) -> None:
        self._reload()
        self._reload_esiti()

    def _modifica_esito(self, riga: dict) -> None:
        # Riferimento tenuto su self, stesso motivo di _import_modal sopra.
        self._esito_modal = RegistraEsitoModal(riga, self._gestore_rendicontazione, esito_id=riga["esito_id"])
        self._esito_modal.esitoRegistrato.connect(self._on_esito_registrato)
        self._esito_modal.show_over(self)

    def _elimina_esito(self, riga: dict) -> None:
        # Conferma esplicita richiesta dall'utente prima di procedere (stesso pattern gia' usato
        # su Camion/Dipendenti/Ordini): qui l'eliminazione e' definitiva (elimina_esito rimuove
        # anche le eventuali prove allegate e riporta l'ordine allo stato precedente).
        modale = ConfirmModal(
            "Elimina esito",
            f"Sei sicuro di voler eliminare l'esito registrato per l'ordine {riga['id']} "
            f"({riga['cliente']})? L'eliminazione è definitiva: le eventuali prove allegate "
            "verranno rimosse e l'ordine tornerà allo stato precedente alla registrazione.",
        )
        modale.confirmed.connect(lambda: self._conferma_elimina_esito(riga))
        modale.show_over(self)

    def _conferma_elimina_esito(self, riga: dict) -> None:
        risultato = self._gestore_rendicontazione.elimina_esito(riga["esito_id"])
        if not risultato.ok:
            self._toasts.show_error("Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()
        self._reload_esiti()

    # --- gestori eventi: tab Esiti -------------------------------------------------------------

    def _on_esiti_filtro_cambiato(self, *_args) -> None:
        self._esiti_pagina_corrente = 1
        self._reload_esiti()

    def _on_esiti_data_filtro_cambiata(self, valore: QDate) -> None:
        self._esiti_filtro_data = valore.toPython()
        self._on_esiti_filtro_cambiato()

    def _on_esiti_sort_richiesto(self, colonna: str, ascending: bool) -> None:
        self._esiti_decrescente = not ascending
        self._reload_esiti()

    def _on_esiti_pagina_richiesta(self, pagina: int) -> None:
        self._esiti_pagina_corrente = pagina
        self._reload_esiti()

    def _esiti_ripristina_filtri(self) -> None:
        self._esiti_campo_ricerca.set_value("")
        self._esiti_select_esito.set_value([])
        self._esiti_campo_data.set_value(QDate.currentDate())
        self._esiti_filtro_data = None
        self._esiti_pagina_corrente = 1
        self._reload_esiti()
