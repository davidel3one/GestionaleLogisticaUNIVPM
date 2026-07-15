"""Pagina Ordini: TabBar (Ordini/Esiti) + PageHeader + Filter Card + Table (fonte: mockup Sketch,
artboard "Ordini").

Scope di questa prima passata (decisione esplicita dell'utente): solo lista/filtri/tabella.
- Tab "Esiti" visibile ma disabilitata: non ancora collegata al lavoro RF15-RF18.
- Bottone header "Importa CSV" visibile ma disabilitato: il flusso a 2 passi (seleziona file →
  riepilogo risultato) richiede componenti non ancora costruiti (file-picker, riepilogo errori).
- Nessuna colonna Azioni: l'icona matita del mockup apre in realtà "Registra esito consegna"
  (Completato/Fallito + causale + upload prova, cfr. GestoreRendicontazione.registra_esito), una
  feature a parte non ancora costruita - niente icona finta senza comportamento.
- Colonna "colli" omessa: nessun campo corrispondente nel modello Ordine, il mockup la mostra ma
  non corrisponde a nulla di reale.
"""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    DatePicker,
    LinkButton,
    PageHeader,
    SearchField,
    Select,
    TabBar,
    Table,
    TextEmphasis,
    load_lucide_icon,
)
from gestionale_logistica.logistica.gestore_logistica import (
    FILTRO_TUTTI,
    STATO_ORDINE_LABELS,
    GestoreLogistica,
)

PAGE_SIZE = 12

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15


def _formatta_numero(valore: float) -> str:
    return str(int(valore)) if valore == int(valore) else str(valore)


def _formatta_peso_volume(peso: float, volume_cargo: float) -> str:
    return f"{_formatta_numero(peso)} kg · {_formatta_numero(volume_cargo)} m³"


class OrdiniPage(QWidget):
    def __init__(self, gestore: GestoreLogistica, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gestore = gestore
        self._pagina_corrente = 1
        self._decrescente = False
        self._filtro_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        self._costruisci_tab_bar(layout)
        self._costruisci_header(layout)
        self._costruisci_filtri(layout)
        self._costruisci_tabella(layout)

        self._reload()

    # --- costruzione UI -------------------------------------------------------------

    def _costruisci_tab_bar(self, layout: QVBoxLayout) -> None:
        layout.addWidget(TabBar(["Ordini", "Esiti"], disabled={1}))

    def _costruisci_header(self, layout: QVBoxLayout) -> None:
        # "Importa CSV" apre un flusso a 2 passi non ancora costruito (file-picker + riepilogo
        # risultato/errori) - visibile ma disabilitato per ora, stesso trattamento gia' deciso
        # per "Nuova pianificazione" in Viaggi.
        bottone_importa = Button(
            ButtonVariant.SECONDARY_HEADER_ADD,
            "Importa CSV",
            load_lucide_icon("upload", "#2E2E2E", 15),
        )
        bottone_importa.setEnabled(False)
        layout.addWidget(PageHeader("Ordini", [bottone_importa]))

    def _costruisci_filtri(self, layout: QVBoxLayout) -> None:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca cliente, indirizzo, ID...")
        self._select_stato = Select(
            "Stato", options=list(STATO_ORDINE_LABELS.values()), placeholder="Tutti"
        )
        self._campo_data = DatePicker("Data")
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._campo_data)
        riga.addStretch(1)

        self._etichetta_conteggio = QLabel()
        self._etichetta_conteggio.setStyleSheet("color: #5A6372;")
        riga.addWidget(self._etichetta_conteggio)

        link_ripristina = LinkButton("Ripristina filtri", "rotate-ccw")
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
                ColumnDef(key="id", label="ID", column_type=ColumnType.LINK, stretch=1),
                ColumnDef(key="cliente", label="Cliente", stretch=1),
                ColumnDef(key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=2),
                # Etichetta "Arrivo viaggio" invece del semplice "DATA" del mockup: il valore
                # viene da Viaggio.data_arrivo_prevista, non e' una data propria dell'ordine -
                # va reso inequivocabile nell'interfaccia (decisione dell'utente), non solo un
                # valore nudo indistinguibile da un'ipotetica data ordine.
                ColumnDef(key="arrivo_viaggio", label="Arrivo viaggio", sortable=True, stretch=1),
                ColumnDef(
                    key="peso_volume", label="Peso / Volume", emphasis=TextEmphasis.SECONDARY, stretch=1
                ),
                ColumnDef(key="stato", label="Stato", column_type=ColumnType.STATUS_BADGE, stretch=1),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella)

    # --- dati -------------------------------------------------------------

    def _reload(self) -> None:
        pagina = self._gestore.visualizza_ordini(
            ricerca=self._campo_ricerca.value() or None,
            filtro_stato=self._select_stato.value() or FILTRO_TUTTI,
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
                "arrivo_viaggio": r.data_arrivo_viaggio.strftime("%d/%m/%Y") if r.data_arrivo_viaggio else "—",
                "peso_volume": _formatta_peso_volume(r.peso, r.volume_cargo),
                "stato": r.stato,
            }
            for r in pagina.ordini
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} ordini")

    # --- gestori eventi -------------------------------------------------------------

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
        self._select_stato.set_value(None)
        self._campo_data.set_value(QDate.currentDate())
        self._filtro_data = None
        self._pagina_corrente = 1
        self._reload()
