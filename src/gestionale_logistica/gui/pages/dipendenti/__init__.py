"""Pagina Dipendenti: PageHeader + Filter Card + Table + Modal aggiungi (fonte: mockup Sketch,
artboard "Dipendenti" / "Dipendenti — Aggiungi (modale)")."""

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
    TextField,
    load_lucide_icon,
)
from gestionale_logistica.risorse.gestore_dipendenti import (
    FILTRO_TUTTI,
    STATO_ATTIVO,
    STATO_CESSATO,
    STATO_IN_VIAGGIO,
    GestoreDipendenti,
)

PAGE_SIZE = 12

FILTRO_TUTTE_SQUADRE = "Tutte le squadre"

# Sì/No per il filtro Certificazione gas (non nel mockup, aggiunto su richiesta esplicita
# dell'utente) - stesse etichette gia' usate da BooleanToggle per coerenza visiva.
CERT_GAS_SI = "Sì"
CERT_GAS_NO = "No"

STATO_BADGE_COLORS = {
    STATO_IN_VIAGGIO: ("#FEF2C6", "#B45208"),
    STATO_CESSATO: ("#FBE4E1", "#BF392A"),
}

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15


def _qdate_a_datetime(valore: QDate) -> datetime:
    data = valore.toPython()
    return datetime(data.year, data.month, data.day)


class DipendentiPage(QWidget):
    def __init__(self, gestore: GestoreDipendenti, parent: QWidget | None = None) -> None:
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
            "Aggiungi dipendente",
            load_lucide_icon("circle-plus", "#2E2E2E", 15),
        )
        bottone_aggiungi.clicked.connect(self._apri_modale_aggiungi)
        layout.addWidget(PageHeader("Dipendenti", [bottone_aggiungi]))

    def _costruisci_filtri(self, layout: QVBoxLayout) -> None:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca dipendente...")
        # FILTRO_TUTTE_SQUADRE/FILTRO_TUTTI compaiono come prima voce selezionabile nel popup
        # (non solo come placeholder): senza una voce esplicita per "nessun filtro" non c'e' modo
        # di tornare a vedere tutti dopo aver scelto una squadra/stato specifico, dato che il
        # popup di Select mostra solo le option passate qui.
        self._select_squadra = Select(
            "Squadra", options=[FILTRO_TUTTE_SQUADRE, *self._opzioni_squadra()], placeholder="Tutte"
        )
        self._select_stato = Select(
            "Stato",
            options=[FILTRO_TUTTI, STATO_ATTIVO, STATO_IN_VIAGGIO, STATO_CESSATO],
            placeholder="Tutti",
        )
        self._select_cert_gas = Select(
            "Cert. gas", options=[CERT_GAS_SI, CERT_GAS_NO], placeholder="Tutti"
        )
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_squadra)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._select_cert_gas)
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
        self._select_squadra.valueChanged.connect(self._on_filtro_cambiato)
        self._select_stato.valueChanged.connect(self._on_filtro_cambiato)
        self._select_cert_gas.valueChanged.connect(self._on_filtro_cambiato)

    def _costruisci_tabella(self, layout: QVBoxLayout) -> None:
        self._tabella = Table(
            [
                ColumnDef(key="nome", label="Nome", stretch=2),
                ColumnDef(key="codice_fiscale", label="Codice fiscale", stretch=2),
                ColumnDef(key="squadra_corrente", label="Squadra", stretch=1),
                ColumnDef(key="data_assunzione", label="Assunzione", sortable=True, stretch=1),
                ColumnDef(
                    key="flg_certificazione_gas",
                    label="Cert. gas",
                    column_type=ColumnType.BOOLEAN_BADGE,
                    stretch=1,
                ),
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
                        RowAction("pencil", self._apri_modale_modifica, tooltip="Modifica"),
                        RowAction("trash-2", self._elimina_riga),
                    ],
                ),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella)

    # --- dati -------------------------------------------------------------

    def _opzioni_squadra(self) -> list[str]:
        pagina_completa = self._gestore.visualizza_dipendenti(dimensione_pagina=0)
        squadre = {r.squadra_corrente for r in pagina_completa.dipendenti if r.squadra_corrente != "—"}
        return sorted(squadre)

    def _reload(self) -> None:
        squadra_selezionata = self._select_squadra.value()
        if squadra_selezionata == FILTRO_TUTTE_SQUADRE:
            squadra_selezionata = None

        cert_gas_selezionato = self._select_cert_gas.value()
        filtro_cert_gas = {CERT_GAS_SI: True, CERT_GAS_NO: False}.get(cert_gas_selezionato)

        pagina = self._gestore.visualizza_dipendenti(
            ricerca=self._campo_ricerca.value() or None,
            filtro_squadra=squadra_selezionata,
            filtro_stato=self._select_stato.value() or FILTRO_TUTTI,
            filtro_certificazione_gas=filtro_cert_gas,
            pagina=self._pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._decrescente,
        )
        righe = [
            {
                "id": r.id,
                "nome": f"{r.nome} {r.cognome}",
                "codice_fiscale": r.codice_fiscale,
                "squadra_corrente": r.squadra_corrente,
                "data_assunzione": r.data_assunzione.strftime("%d/%m/%Y"),
                "flg_certificazione_gas": r.flg_certificazione_gas,
                "stato": r.stato,
            }
            for r in pagina.dipendenti
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} dipendenti")

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
        self._select_squadra.set_value(None)
        self._select_stato.set_value(None)
        self._select_cert_gas.set_value(None)
        self._pagina_corrente = 1
        self._reload()

    def _elimina_riga(self, riga: dict) -> None:
        # Soft-delete (stesso comportamento di licenzia_dipendente sul pulsante modifica quando la
        # riga e' attiva) - non elimina i dati, preserva lo storico (RF8).
        risultato = self._gestore.licenzia_dipendente(riga["id"])
        if not risultato.ok:
            QMessageBox.warning(self, "Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    # --- modali -------------------------------------------------------------

    def _apri_modale_aggiungi(self) -> None:
        campo_nome = TextField("Nome", placeholder="es. Mario")
        campo_cognome = TextField("Cognome", placeholder="es. Rossi")
        campo_cf = TextField("Codice fiscale", placeholder="es. RSSMRA85M01A271X")
        campo_data = DatePicker("Data assunzione")
        campo_gas = BooleanToggle("Certificazione gas")

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Aggiungi dipendente")
        modale = Modal(
            "Aggiungi dipendente", width=560, footer_buttons=[bottone_annulla, bottone_conferma]
        )
        for campo in (campo_nome, campo_cognome, campo_cf, campo_data, campo_gas):
            modale.add_widget(campo)

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            codice_fiscale = campo_cf.value().strip()
            risultato = self._gestore.inserisci_dipendente(
                id_=codice_fiscale,
                nome=campo_nome.value().strip(),
                cognome=campo_cognome.value().strip(),
                codice_fiscale=codice_fiscale,
                data_assunzione=_qdate_a_datetime(campo_data.value()),
                flg_certificazione_gas=campo_gas.value(),
            )
            if risultato.ok:
                modale.close()
                self._reload()
            else:
                # Stesso principio del feedback su licenzia_dipendente rifiutato: senza questo,
                # un codice fiscale mal formato (o gia' registrato) sembrerebbe un bottone che
                # non fa nulla.
                QMessageBox.warning(
                    self, "Impossibile aggiungere", risultato.motivo or "Operazione rifiutata."
                )

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)

    def _apri_modale_modifica(self, riga: dict) -> None:
        # Stato attuale come booleano attivo/non-attivo: "In viaggio" conta come attivo (stessa
        # equivalenza gia' usata dal precedente toggle diretto della matita) - serve per capire se
        # il salvataggio deve davvero chiamare licenzia/riassumi o se lo stato scelto coincide gia'
        # con quello corrente (nessuna chiamata, altrimenti riassumi_dipendente rifiuterebbe un
        # dipendente gia' attivo).
        era_attivo = riga["stato"] != STATO_CESSATO

        campo_stato = Select("Stato", options=[STATO_ATTIVO, STATO_CESSATO], placeholder=STATO_ATTIVO)
        campo_stato.set_value(STATO_ATTIVO if era_attivo else STATO_CESSATO)
        campo_gas = BooleanToggle("Certificazione gas")
        campo_gas.set_value(riga["flg_certificazione_gas"])

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Salva")
        modale = Modal(
            f"Modifica dipendente — {riga['nome']}", width=560,
            footer_buttons=[bottone_annulla, bottone_conferma],
        )
        modale.add_widget(campo_stato)
        modale.add_widget(campo_gas)

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            nuovo_attivo = campo_stato.value() == STATO_ATTIVO
            if nuovo_attivo != era_attivo:
                if nuovo_attivo:
                    risultato = self._gestore.riassumi_dipendente(riga["id"])
                    titolo_errore = "Impossibile riassumere"
                else:
                    risultato = self._gestore.licenzia_dipendente(riga["id"])
                    titolo_errore = "Impossibile licenziare"
                if not risultato.ok:
                    QMessageBox.warning(self, titolo_errore, risultato.motivo or "Operazione rifiutata.")
                    return

            if campo_gas.value() != riga["flg_certificazione_gas"]:
                risultato = self._gestore.modifica_dipendente(
                    riga["id"], flg_certificazione_gas=campo_gas.value()
                )
                if not risultato.ok:
                    QMessageBox.warning(
                        self, "Impossibile salvare", risultato.motivo or "Operazione rifiutata."
                    )
                    return

            modale.close()
            self._reload()

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)
