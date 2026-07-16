"""Pagina Squadre: PageHeader + Filter Card + Table + Modal aggiungi/dettaglio (fonte: mockup
Sketch, artboard "Squadre" / "Squadre — Aggiungi (modale)" / "Squadre — Dettaglio (modale)" /
"Squadre — Dettaglio vuoto (modale)").

Il dettaglio READ-ONLY (membri/camion/stato + storico viaggi) si apre cliccando l'ID della squadra
(colonna LINK), non piu' da un'icona "modifica": quella ora cambia solo lo stato della squadra
(elimina/riattiva) - icona "arrow-left-right" verde/rossa in base allo stato (2026-07-16, su
richiesta esplicita dell'utente, stessa icona gia' usata da Camion per lo stesso pattern), stesso
redesign applicato a tutti i domini (vedi componenti-gui.md)."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from sqlalchemy import select

from gestionale_logistica.database.enums import StatoViaggio
from gestionale_logistica.database.models import Camion, Dipendente
from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    Card,
    ColumnDef,
    ColumnType,
    EmptyState,
    LinkButton,
    Modal,
    MultiSelect,
    PageHeader,
    RowAction,
    SearchField,
    Select,
    Table,
    TextEmphasis,
    ToastManager,
    load_lucide_icon,
)
from gestionale_logistica.risorse.gestore_squadre import (
    STATO_ATTIVA,
    STATO_IN_VIAGGIO,
    STATO_NON_ATTIVA,
    GestoreSquadre,
)

PAGE_SIZE = 20

STATO_BADGE_COLORS = {
    STATO_IN_VIAGGIO: ("#FEF2C6", "#B45208"),
    # "Attiva" (femminile, concorda con "squadra") va mappato esplicitamente: la palette di
    # default di Table ha solo "Attivo" (maschile, usata da Dipendenti/Camion) - "Attiva" da sola
    # non ci farebbe match e cadrebbe silenziosamente sul grigio neutro di fallback (bug reale
    # trovato in verifica visiva, non un'assunzione preventiva).
    STATO_ATTIVA: ("#DFF5E5", "#1E8E3E"),
    # "Non attiva" non ha bisogno di un override: coincide gia' con il grigio neutro di fallback.
}

# Etichette italiane per lo storico viaggi nel modale Dettaglio: stessa necessita' gia' incontrata
# per la lista Viaggi (gli enum StatoViaggio sono CamelCase, pensati per la persistenza).
STATO_VIAGGIO_LABELS: dict[StatoViaggio, str] = {
    StatoViaggio.IN_COMPOSIZIONE: "In composizione",
    StatoViaggio.PIANIFICATO: "Pianificato",
    StatoViaggio.IN_CORSO: "In corso",
    StatoViaggio.COMPLETATO: "Completato",
    StatoViaggio.ANNULLATO: "Annullato",
}

STATO_VIAGGIO_BADGE_COLORS = {
    STATO_VIAGGIO_LABELS[StatoViaggio.IN_CORSO]: ("#FEF3C7", "#B45309"),
    STATO_VIAGGIO_LABELS[StatoViaggio.COMPLETATO]: ("#DFF5E5", "#1E8E3E"),
    STATO_VIAGGIO_LABELS[StatoViaggio.ANNULLATO]: ("#FBE4E1", "#C0392B"),
}

FILTER_TITLE_COLOR = "#2D2D2D"
FILTER_TITLE_SIZE = 15

# Non nel mockup, aggiunti su richiesta esplicita dell'utente - stessa coppia Sì/No gia' usata
# per i filtri Cert. gas (Dipendenti) e Sponda idraulica (Camion), per coerenza tra le pagine.
CERT_GAS_SI = "Sì"
CERT_GAS_NO = "No"
SPONDA_SI = "Sì"
SPONDA_NO = "No"


class SquadrePage(QWidget):
    def __init__(self, gestore: GestoreSquadre, parent: QWidget | None = None) -> None:
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

        self._toasts = ToastManager(self)

        self._reload()

    # --- costruzione UI -------------------------------------------------------------

    def _costruisci_header(self, layout: QVBoxLayout) -> None:
        bottone_aggiungi = Button(
            ButtonVariant.SECONDARY_HEADER_ADD,
            "Nuova squadra",
            load_lucide_icon("circle-plus", "#2E2E2E", 15),
        )
        bottone_aggiungi.clicked.connect(self._apri_modale_aggiungi)
        layout.addWidget(PageHeader("Squadre", [bottone_aggiungi]))

    def _costruisci_filtri(self, layout: QVBoxLayout) -> None:
        card = Card(padding_horizontal=24, padding_vertical=20, spacing=16)

        titolo = QLabel("Filtri")
        titolo.setStyleSheet(f"color: {FILTER_TITLE_COLOR}; font-size: {FILTER_TITLE_SIZE}px;")
        card.add_widget(titolo)

        riga = QHBoxLayout()
        riga.setSpacing(16)

        self._campo_ricerca = SearchField(placeholder="Cerca dipendente, camion...")
        # Filtro a scelta multipla (2026-07-16, su richiesta esplicita dell'utente): vedi la stessa
        # nota in gui/pages/dipendenti/__init__.py.
        self._select_stato = MultiSelect(
            "Stato",
            options=[STATO_ATTIVA, STATO_IN_VIAGGIO, STATO_NON_ATTIVA],
            placeholder="Tutte",
            compact=True,
        )
        self._select_cert_gas = MultiSelect(
            "Cert. gas", options=[CERT_GAS_SI, CERT_GAS_NO], placeholder="Tutti", compact=True
        )
        self._select_sponda = MultiSelect(
            "Sponda idraulica", options=[SPONDA_SI, SPONDA_NO], placeholder="Tutti", compact=True
        )
        riga.addWidget(self._campo_ricerca, 1)
        riga.addWidget(self._select_stato)
        riga.addWidget(self._select_cert_gas)
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
        self._select_stato.valueChanged.connect(self._on_filtro_cambiato)
        self._select_cert_gas.valueChanged.connect(self._on_filtro_cambiato)
        self._select_sponda.valueChanged.connect(self._on_filtro_cambiato)

    def _costruisci_tabella(self, layout: QVBoxLayout) -> None:
        self._tabella = Table(
            [
                ColumnDef(
                    key="squadra", label="Squadra", column_type=ColumnType.LINK, stretch=1,
                    on_click=self._apri_modale_dettaglio,
                ),
                ColumnDef(key="membri", label="Membri", stretch=2),
                ColumnDef(key="camion", label="Camion", emphasis=TextEmphasis.SECONDARY, stretch=1),
                ColumnDef(key="creazione", label="Creazione", sortable=True, stretch=1),
                # Stesse due colonne booleane gia' usate in Dipendenti ("Cert. gas") e Camion
                # ("Sponda idraulica"): stessa label/ColumnType, riusate qui per coerenza invece
                # di inventare una presentazione nuova (non nel mockup Sketch, che non modella
                # queste colonne su Squadre - vedi CLAUDE.md, regola 7).
                ColumnDef(
                    key="flg_certificazione_gas",
                    label="Cert. gas",
                    column_type=ColumnType.BOOLEAN_BADGE,
                    stretch=1,
                ),
                ColumnDef(
                    key="flg_sponda_idraulica",
                    label="Sponda idraulica",
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
                        # Icona "arrow-left-right" al posto della precedente matita generica
                        # (2026-07-16, su richiesta esplicita dell'utente: stessa icona/colore gia'
                        # usati da Camion per lo stesso identico pattern - toggle Attivo/Dismesso
                        # in un click, senza modale). Solo per Attiva -> Non attiva: per In viaggio
                        # l'icona non compare (bug corretto in bug-bounty: prima il predicate
                        # `!= STATO_NON_ATTIVA` la mostrava anche su righe In viaggio con tooltip
                        # "Attiva" - stato sbagliato - e il click chiamava comunque elimina_squadra,
                        # che rifiuta sempre una squadra coinvolta in un viaggio in corso, quindi
                        # l'azione offerta non poteva mai riuscire).
                        RowAction(
                            "arrow-left-right", self._modifica_riga, color="#1E8E3E",
                            tooltip="Attiva — clicca per disattivare",
                            predicate=lambda riga: riga["stato"] == STATO_ATTIVA,
                        ),
                        RowAction(
                            "arrow-left-right", self._modifica_riga, color="#BF392A",
                            tooltip="Non attiva — clicca per riattivare",
                            predicate=lambda riga: riga["stato"] == STATO_NON_ATTIVA,
                        ),
                        RowAction("trash-2", self._elimina_riga),
                    ],
                ),
            ]
        )
        self._tabella.sortRequested.connect(self._on_sort_richiesto)
        self._tabella.pageChanged.connect(self._on_pagina_richiesta)
        layout.addWidget(self._tabella, 1)

    # --- dati -------------------------------------------------------------

    def _opzioni_camion(self) -> dict[str, str]:
        """Mappa targa -> id per i camion attivi, per popolare la Select del modale Aggiungi."""
        with self._gestore.session_factory() as session:
            camion = session.scalars(select(Camion).where(Camion.flg_attivo.is_(True))).all()
        return {c.targa: c.id for c in camion}

    def _opzioni_dipendenti(self) -> dict[str, str]:
        """Mappa 'Nome Cognome (id)' -> id per i dipendenti attivi. Il suffisso con l'id evita
        ambiguita' se due dipendenti condividono lo stesso nome completo (targa camion e' invece
        gia' unica di suo, non serve lo stesso trattamento)."""
        with self._gestore.session_factory() as session:
            dipendenti = session.scalars(select(Dipendente).where(Dipendente.flg_attivo.is_(True))).all()
        return {f"{d.nome} {d.cognome} ({d.id})": d.id for d in dipendenti}

    def _prossimo_id_squadra(self) -> str:
        return self._gestore.prossimo_id_squadra()

    def _reload(self) -> None:
        # Certificazione gas/sponda idraulica restano booleani lato backend: la GUI riduce la
        # selezione multipla Sì/No a un singolo bool (una sola etichetta selezionata) o None
        # (zero o entrambe) - stesso pattern gia' usato per il filtro Sponda idraulica in Camion.
        valori_cert_gas = self._select_cert_gas.value()
        filtro_cert_gas = valori_cert_gas[0] == CERT_GAS_SI if len(valori_cert_gas) == 1 else None
        valori_sponda = self._select_sponda.value()
        filtro_sponda = valori_sponda[0] == SPONDA_SI if len(valori_sponda) == 1 else None

        pagina = self._gestore.visualizza_squadre(
            ricerca=self._campo_ricerca.value() or None,
            filtro_stato=self._select_stato.value(),
            filtro_certificazione_gas=filtro_cert_gas,
            filtro_sponda_idraulica=filtro_sponda,
            pagina=self._pagina_corrente,
            dimensione_pagina=PAGE_SIZE,
            decrescente=self._decrescente,
        )
        # "Squadra" mostra un numero progressivo di posizione, non l'id reale a DB: cosi' la lista
        # resta senza buchi anche quando una squadra viene eliminata (l'id vero, usato per le azioni,
        # resta comunque in "id" - vedi _elimina_riga/_apri_modale_dettaglio).
        numero_base = max(self._pagina_corrente - 1, 0) * PAGE_SIZE
        righe = [
            {
                "id": r.id,
                "squadra": f"#{numero_base + indice + 1}",
                "membri": r.membri,
                "camion": r.camion,
                "creazione": r.data_creazione.strftime("%d/%m/%Y"),
                "flg_certificazione_gas": r.flg_certificazione_gas,
                "flg_sponda_idraulica": r.flg_sponda_idraulica,
                "stato": r.stato,
            }
            for indice, r in enumerate(pagina.squadre)
        ]
        self._tabella.set_rows(righe)
        self._tabella.set_pagination(self._pagina_corrente, pagina.totale, PAGE_SIZE)
        self._etichetta_conteggio.setText(f"{pagina.totale} squadre")

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
        self._select_stato.set_value([])
        self._select_cert_gas.set_value([])
        self._select_sponda.set_value([])
        self._pagina_corrente = 1
        self._reload()

    def _modifica_riga(self, riga: dict) -> None:
        # Il pulsante modifica cambia solo lo stato: da Non attiva riattiva, da Attiva/In viaggio
        # elimina (soft-delete - la squadra sparisce dalla vista di default ma resta recuperabile
        # filtrando per Stato "Non attiva").
        if riga["stato"] == STATO_NON_ATTIVA:
            risultato = self._gestore.riattiva_squadra(riga["id"])
            titolo_errore = "Impossibile riattivare"
        else:
            risultato = self._gestore.elimina_squadra(riga["id"])
            titolo_errore = "Impossibile eliminare"
        if not risultato.ok:
            self._toasts.show_error(titolo_errore, risultato.motivo or "Operazione rifiutata.")
        self._reload()

    def _elimina_riga(self, riga: dict) -> None:
        # Soft-delete (stesso comportamento di elimina_squadra sul pulsante modifica quando la
        # riga e' attiva) - non elimina i dati, preserva lo storico (RF8).
        risultato = self._gestore.elimina_squadra(riga["id"])
        if not risultato.ok:
            self._toasts.show_error("Impossibile eliminare", risultato.motivo or "Operazione rifiutata.")
        self._reload()

    # --- modali -------------------------------------------------------------

    def _apri_modale_aggiungi(self) -> None:
        opzioni_camion = self._opzioni_camion()
        opzioni_dipendenti = self._opzioni_dipendenti()

        campo_camion = Select("Camion", options=list(opzioni_camion), placeholder="Seleziona camion disponibile")
        campo_dip_1 = Select(
            "Dipendente 1", options=list(opzioni_dipendenti), placeholder="Seleziona dipendente"
        )
        campo_dip_2 = Select(
            "Dipendente 2", options=list(opzioni_dipendenti), placeholder="Seleziona dipendente"
        )

        bottone_annulla = Button(ButtonVariant.SECONDARY, "Annulla")
        bottone_conferma = Button(ButtonVariant.PRIMARY, "Aggiungi squadra")
        modale = Modal("Aggiungi squadra", width=560, footer_buttons=[bottone_annulla, bottone_conferma])
        for campo in (campo_camion, campo_dip_1, campo_dip_2):
            modale.add_widget(campo)

        bottone_annulla.clicked.connect(modale.close)

        def _conferma() -> None:
            camion_id = opzioni_camion.get(campo_camion.value())
            dip_1_id = opzioni_dipendenti.get(campo_dip_1.value())
            dip_2_id = opzioni_dipendenti.get(campo_dip_2.value())
            if camion_id is None or dip_1_id is None or dip_2_id is None:
                self._toasts.show_error("Impossibile aggiungere", "Seleziona camion e i due dipendenti.")
                return

            nuovo_id = self._prossimo_id_squadra()
            risultato_squadra = self._gestore.crea_squadra(nuovo_id, data_creazione=datetime.now())
            if not risultato_squadra.ok:
                self._toasts.show_error(
                    "Impossibile aggiungere", risultato_squadra.motivo or "Operazione rifiutata."
                )
                return

            risultato_composizione = self._gestore.apri_composizione(
                id_composizione=nuovo_id,
                squadra_id=nuovo_id,
                camion_id=camion_id,
                dipendente_1_id=dip_1_id,
                dipendente_2_id=dip_2_id,
            )
            if risultato_composizione.ok:
                modale.close()
                self._reload()
            else:
                self._toasts.show_error(
                    "Impossibile aggiungere",
                    risultato_composizione.motivo or "Operazione rifiutata.",
                )

        bottone_conferma.clicked.connect(_conferma)
        modale.show_over(self)

    def _apri_modale_dettaglio(self, riga: dict) -> None:
        dettaglio = self._gestore.dettaglio_squadra(riga["id"])
        if dettaglio is None:
            self._toasts.show_error("Squadra non trovata", "La squadra non esiste più.")
            self._reload()
            return

        sottotitolo = f"{dettaglio.membri} · Camion {dettaglio.camion} · {dettaglio.stato}"
        modale = Modal(f"Squadra #{dettaglio.id}", subtitle=sottotitolo, width=900)

        if not dettaglio.viaggi:
            modale.add_widget(
                EmptyState(
                    "Nessun viaggio registrato",
                    "I viaggi assegnati a questa squadra appariranno qui",
                )
            )
        else:
            tabella_viaggi = Table(
                [
                    ColumnDef(key="id_viaggio", label="ID viaggio", column_type=ColumnType.LINK, stretch=1),
                    ColumnDef(key="n_ordini", label="N. ordini", emphasis=TextEmphasis.SECONDARY, stretch=1),
                    ColumnDef(
                        key="stato",
                        label="Stato",
                        column_type=ColumnType.STATUS_BADGE,
                        status_colors=STATO_VIAGGIO_BADGE_COLORS,
                        stretch=1,
                    ),
                    ColumnDef(key="data", label="Data", stretch=1),
                ]
            )
            righe_viaggi = [
                {
                    "id_viaggio": v.id_viaggio,
                    "n_ordini": f"{v.n_ordini} ordini",
                    "stato": STATO_VIAGGIO_LABELS[v.stato_viaggio],
                    "data": v.data_partenza_prevista.strftime("%d/%m/%Y"),
                }
                for v in dettaglio.viaggi
            ]
            tabella_viaggi.set_rows(righe_viaggi)
            tabella_viaggi.set_pagination(1, len(righe_viaggi), max(len(righe_viaggi), 1))
            modale.add_widget(tabella_viaggi)

        modale.show_over(self)
