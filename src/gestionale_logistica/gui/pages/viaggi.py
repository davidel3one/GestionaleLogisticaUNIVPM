"""Pagina Viaggi: PageHeader + Filter Card + Table + Modal modifica date (fonte: mockup Sketch,
artboard "Viaggi").

Divergenza dichiarata dal mockup: non esiste un artboard "Viaggi — Modifica (modale)" ne'
un'operazione di modifica viaggio nelle RF, ma la tabella disegna comunque un'icona matita per
riga. Su decisione esplicita dell'utente, l'icona apre qui un modale minimale che permette di
correggere solo le due date previste (partenza/arrivo) — l'unico dato semplice modificabile senza
toccare composizione/ordini, che invece resta fuori scope finche' non esiste la procedura di
pianificazione vera e propria."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    DatePicker,
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
    STATO_VIAGGIO_LABELS,
    GestoreLogistica,
)

PAGE_SIZE = 12

STATO_BADGE_COLORS = {
    STATO_VIAGGIO_LABELS[StatoViaggio.IN_CORSO]: ("#FEF3C7", "#B45309"),
    STATO_VIAGGIO_LABELS[StatoViaggio.COMPLETATO]: ("#DFF5E5", "#1E8E3E"),
    STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO]: ("#FBE4E1", "#C0392B"),
    # "Pianificato" e "In composizione" non hanno bisogno di un override: coincidono gia'
    # esattamente con la palette di default di Table (Pianificato -> blu, In composizione ->
    # grigio neutro di fallback) - verificato pixel per pixel dal mockup, non un'assunzione.
}

STATI_TERMINALI = {
    STATO_VIAGGIO_LABELS[StatoViaggio.COMPLETATO],
    STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO],
}

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15


def _qdate_a_datetime(valore: QDate) -> datetime:
    data = valore.toPython()
    return datetime(data.year, data.month, data.day)


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
                        RowAction("pencil", self._apri_modale_modifica),
                        RowAction(
                            "trash-2",
                            self._annulla_riga,
                            tooltip="Annulla viaggio",
                            predicate=lambda r: r["stato"] not in STATI_TERMINALI,
                        ),
                        RowAction(
                            "rotate-ccw",
                            self._ripristina_riga,
                            tooltip="Ripristina viaggio",
                            predicate=lambda r: r["stato"]
                            == STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO],
                        ),
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
                "squadra": f"Squadra {r.squadra_id}",
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

    def _annulla_riga(self, riga: dict) -> None:
        risultato = self._gestore.annulla_viaggio(riga["id"])
        if not risultato.ok:
            QMessageBox.warning(self, "Impossibile annullare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    def _ripristina_riga(self, riga: dict) -> None:
        risultato = self._gestore.ripristina_viaggio(riga["id"])
        if not risultato.ok:
            QMessageBox.warning(self, "Impossibile ripristinare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    # --- modali -------------------------------------------------------------

    def _apri_modale_modifica(self, riga: dict) -> None:
        campo_partenza = DatePicker("Data partenza prevista")
        campo_arrivo = DatePicker("Data arrivo prevista")

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Salva")
        modale = Modal(
            f"Modifica date — {riga['id']}", width=560, footer_buttons=[bottone_annulla, bottone_conferma]
        )
        modale.content_layout.addLayout(riga_2_colonne(campo_partenza, campo_arrivo))

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            risultato = self._gestore.modifica_date_viaggio(
                riga["id"],
                data_partenza_prevista=_qdate_a_datetime(campo_partenza.value()),
                data_arrivo_prevista=_qdate_a_datetime(campo_arrivo.value()),
            )
            if risultato.ok:
                modale.close()
                self._reload()
            else:
                QMessageBox.warning(
                    self, "Impossibile salvare", risultato.motivo or "Operazione rifiutata."
                )

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)
