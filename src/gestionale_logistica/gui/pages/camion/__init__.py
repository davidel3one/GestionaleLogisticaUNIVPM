"""Pagina Camion: PageHeader + Filter Card + Table + Modal aggiungi/modifica (fonte: mockup
Sketch, artboard "Camion" / "Camion — Aggiungi (modale)")."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from gestionale_logistica.gui.components import (
    BooleanToggle,
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
    TextField,
    load_lucide_icon,
)
from gestionale_logistica.gui.pages._form_layout import riga_2_colonne
from gestionale_logistica.risorse.gestore_camion import (
    FILTRO_TUTTI,
    STATO_ATTIVO,
    STATO_DISMESSO,
    STATO_IN_VIAGGIO,
    TIPI_MEZZO_NOTI,
    GestoreCamion,
)

PAGE_SIZE = 12

STATO_BADGE_COLORS = {
    STATO_IN_VIAGGIO: ("#FEF2C6", "#B45208"),
    STATO_DISMESSO: ("#FBE4E1", "#BF392A"),
}

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15

SPONDA_SI = "Sì"
SPONDA_NO = "No"


def _qdate_a_datetime(valore: QDate) -> datetime:
    data = valore.toPython()
    return datetime(data.year, data.month, data.day)


def _formatta_numero(valore: float) -> str:
    return str(int(valore)) if valore == int(valore) else str(valore)


def _formatta_capacita(peso_massimo: float, volume_massimo: float) -> str:
    return f"{_formatta_numero(peso_massimo)} kg · {_formatta_numero(volume_massimo)} m³"


class CamionPage(QWidget):
    def __init__(self, gestore: GestoreCamion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gestore = gestore
        self._pagina_corrente = 1
        self._decrescente = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        self._costruisci_header(layout)
        self._costruisci_filtri(layout)
        self._costruisci_tabella(layout)

        self._reload()

    # --- costruzione UI -------------------------------------------------------------

    def _costruisci_header(self, layout: QVBoxLayout) -> None:
        bottone_aggiungi = Button(
            ButtonVariant.SECONDARY_HEADER_ADD,
            "Aggiungi camion",
            load_lucide_icon("circle-plus", "#2E2E2E", 15),
        )
        bottone_aggiungi.clicked.connect(self._apri_modale_aggiungi)
        layout.addWidget(PageHeader("Camion", [bottone_aggiungi]))

    def _costruisci_filtri(self, layout: QVBoxLayout) -> None:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca targa...")
        self._select_tipo = Select("Tipo", options=self._opzioni_tipo_mezzo(), placeholder="Tutti")
        self._select_stato = Select(
            "Stato", options=[STATO_ATTIVO, STATO_IN_VIAGGIO, STATO_DISMESSO], placeholder="Tutti"
        )
        # Non nel mockup, aggiunto su richiesta esplicita dell'utente - stessa coppia Sì/No gia'
        # usata per il filtro Cert. gas in Dipendenti, per coerenza visiva tra le pagine.
        self._select_sponda = Select(
            "Sponda idraulica", options=[SPONDA_SI, SPONDA_NO], placeholder="Tutti"
        )
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_tipo)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._select_sponda)
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
        self._select_tipo.valueChanged.connect(self._on_filtro_cambiato)
        self._select_stato.valueChanged.connect(self._on_filtro_cambiato)
        self._select_sponda.valueChanged.connect(self._on_filtro_cambiato)

    def _costruisci_tabella(self, layout: QVBoxLayout) -> None:
        self._tabella = Table(
            [
                ColumnDef(key="targa", label="Targa", stretch=1),
                ColumnDef(key="tipo_mezzo", label="Tipo mezzo", stretch=1),
                ColumnDef(
                    key="capacita", label="Capacità", emphasis=TextEmphasis.SECONDARY, stretch=1
                ),
                ColumnDef(
                    key="flg_sponda_idraulica",
                    label="Sponda idraulica",
                    column_type=ColumnType.BOOLEAN_BADGE,
                    stretch=1,
                ),
                ColumnDef(key="data_acquisizione", label="Acquisizione", sortable=True, stretch=1),
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
                        # Switch al posto della matita (non nel mockup, richiesto esplicitamente):
                        # stesso identico comportamento del precedente _modifica_riga, solo un
                        # controllo diverso - on/off invece di un'icona su cui cliccare.
                        RowAction(
                            is_switch=True,
                            switch_value=lambda riga: riga["stato"] != STATO_DISMESSO,
                            callback=self._modifica_riga,
                            tooltip="Attivo/Dismesso",
                        ),
                        RowAction("trash-2", self._elimina_riga),
                    ],
                ),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella)

    # --- dati -------------------------------------------------------------

    def _opzioni_tipo_mezzo(self) -> list[str]:
        pagina_completa = self._gestore.visualizza_camion(dimensione_pagina=0)
        tipi_in_uso = {r.tipo_mezzo for r in pagina_completa.camion}
        return sorted(set(TIPI_MEZZO_NOTI) | tipi_in_uso)

    def _reload(self) -> None:
        sponda_selezionata = self._select_sponda.value()
        filtro_sponda = {SPONDA_SI: True, SPONDA_NO: False}.get(sponda_selezionata)

        pagina = self._gestore.visualizza_camion(
            ricerca=self._campo_ricerca.value() or None,
            filtro_tipo=self._select_tipo.value(),
            filtro_stato=self._select_stato.value() or FILTRO_TUTTI,
            filtro_sponda_idraulica=filtro_sponda,
            pagina=self._pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._decrescente,
        )
        righe = [
            {
                "id": r.id,
                "targa": r.targa,
                "tipo_mezzo": r.tipo_mezzo,
                "capacita": _formatta_capacita(r.peso_massimo, r.volume_massimo),
                "flg_sponda_idraulica": r.flg_sponda_idraulica,
                "data_acquisizione": r.data_acquisizione.strftime("%d/%m/%Y"),
                "stato": r.stato,
            }
            for r in pagina.camion
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} camion")

    # --- gestori eventi -------------------------------------------------------------

    def _on_filtro_cambiato(self, *_args) -> None:
        self._pagina_corrente = 1
        self._reload()

    def _on_sort_richiesto(self, colonna: str, ascending: bool) -> None:
        self._decrescente = not ascending
        self._reload()

    def _on_pagina_richiesta(self, pagina: int) -> None:
        self._pagina_corrente = pagina
        self._reload()

    def _ripristina_filtri(self) -> None:
        self._campo_ricerca.set_value("")
        self._select_tipo.set_value(None)
        self._select_stato.set_value(None)
        self._select_sponda.set_value(None)
        self._pagina_corrente = 1
        self._reload()

    def _modifica_riga(self, riga: dict) -> None:
        # Il pulsante modifica cambia solo lo stato (Attivo <-> Dismesso), non i campi del mezzo:
        # da Attivo/In viaggio dismette, da Dismesso rimette in servizio.
        if riga["stato"] == STATO_DISMESSO:
            risultato = self._gestore.riattiva_camion(riga["id"])
            titolo_errore = "Impossibile riattivare"
        else:
            risultato = self._gestore.disattiva_camion(riga["id"])
            titolo_errore = "Impossibile dismettere"
        if not risultato.ok:
            QMessageBox.warning(self, titolo_errore, risultato.motivo or "Operazione rifiutata.")
        self._reload()

    def _elimina_riga(self, riga: dict) -> None:
        # Soft-delete (stesso comportamento di disattiva_camion sul pulsante modifica quando la
        # riga e' attiva) - non elimina i dati, preserva lo storico (RF8).
        risultato = self._gestore.disattiva_camion(riga["id"])
        if not risultato.ok:
            QMessageBox.warning(self, "Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    # --- modali -------------------------------------------------------------

    def _apri_modale_aggiungi(self) -> None:
        campo_targa = TextField("Targa", placeholder="es. AB123CD")
        campo_tipo = Select("Tipo mezzo", options=self._opzioni_tipo_mezzo(), placeholder="Furgone")
        campo_peso = TextField("Peso massimo (kg)", placeholder="es. 1200")
        campo_volume = TextField("Volume massimo (m³)", placeholder="es. 8")
        campo_sponda = BooleanToggle("Sponda idraulica")
        campo_data = DatePicker("Data acquisizione")

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Aggiungi camion")
        modale = Modal("Aggiungi camion", width=560, footer_buttons=[bottone_annulla, bottone_conferma])
        modale.content_layout.addLayout(riga_2_colonne(campo_targa, campo_tipo))
        modale.content_layout.addLayout(riga_2_colonne(campo_peso, campo_volume))
        modale.content_layout.addLayout(riga_2_colonne(campo_sponda, campo_data))

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            targa = campo_targa.value().strip()
            tipo_mezzo = campo_tipo.value()
            if not tipo_mezzo:
                QMessageBox.warning(self, "Impossibile aggiungere", "Seleziona un tipo mezzo.")
                return
            try:
                peso_massimo = float(campo_peso.value().strip().replace(",", "."))
                volume_massimo = float(campo_volume.value().strip().replace(",", "."))
            except ValueError:
                # Lacuna nota (validazione inline non ancora un componente di libreria, vedi
                # componenti-gui.md): QMessageBox nativo, stesso principio gia' usato altrove.
                QMessageBox.warning(
                    self, "Impossibile aggiungere", "Peso e volume massimo devono essere numeri."
                )
                return

            risultato = self._gestore.inserisci_camion(
                id_=targa,
                targa=targa,
                tipo_mezzo=tipo_mezzo,
                data_acquisizione=_qdate_a_datetime(campo_data.value()),
                peso_massimo=peso_massimo,
                volume_massimo=volume_massimo,
                flg_sponda_idraulica=campo_sponda.value(),
            )
            if risultato.ok:
                modale.close()
                self._reload()
            else:
                QMessageBox.warning(
                    self, "Impossibile aggiungere", risultato.motivo or "Operazione rifiutata."
                )

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)
