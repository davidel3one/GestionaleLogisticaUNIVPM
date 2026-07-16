"""RegistraEsitoModal: modale "Registra esito consegna" (RF16-RF18), fonte: mockup Sketch,
artboard "Ordini — Registra esito consegna (modale)".

Specifico alla pagina Ordini (non condiviso con Dashboard come `ImportCsvModal`), quindi vive qui
invece che in `gui/components/`.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gestionale_logistica.database.enums import StatoEsito
from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.dropzone import Dropzone
from gestionale_logistica.gui.components.form_field import Select
from gestionale_logistica.gui.components.icons import load_lucide_icon
from gestionale_logistica.gui.components.modal import Modal
from gestionale_logistica.gui.components.toast import ToastManager
from gestionale_logistica.rendicontazione.gestore_rendicontazione import AllegatoVista, GestoreRendicontazione

# Stessi colori semantici gia' usati per gli esiti altrove (icon_chip.py IconChipVariant.GREEN/
# RED, import_csv_modal.py _BADGE_VALIDE/_MOTIVO_ROSSO) - dichiarati qui invece di importati per
# lo stesso motivo gia' documentato in import_csv_modal.py: quei moduli espongono le coppie
# (colore, sfondo) in un ordine legato al loro uso interno, non un token condiviso.
_VERDE_TESTO = "#1E8E3E"
_VERDE_BG = "#DFF5E5"
_ROSSO_TESTO = "#C0392B"
_ROSSO_BG = "#FBE4E1"
_BORDO_INATTIVO = "#E5EAF0"
_TESTO_INATTIVO = "#2E2E2E"
_SUBTITLE_COLOR = "#8A93A0"
_INFO_COLOR = "#8A93A0"

TOGGLE_HEIGHT = 48
TOGGLE_RADIUS = 9
TOGGLE_GAP = 12


class _BottoneEsito(QPushButton):
    """Singolo bottone del toggle Completato/Fallito: bordo+sfondo colorati quando selezionato,
    grigio neutro con icona colorata quando non selezionato (misurato dallo screenshot del
    mockup - il frame disponibile mostra solo lo stato "Fallito selezionato", lo stato
    "Completato selezionato" e' un'estrapolazione simmetrica dichiarata, non misurata)."""

    def __init__(self, testo: str, icona: str, colore: str, colore_bg: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colore = colore
        self._colore_bg = colore_bg
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(TOGGLE_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self._icon_label = QLabel(self)
        self._icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(testo, self)
        font = QFont("Inter")
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(14)
        self._text_label.setFont(font)
        self._text_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._text_label)
        layout.addStretch(1)

        self._icona_nome = icona
        self._aggiorna_stile()
        self.toggled.connect(self._aggiorna_stile)

    def _aggiorna_stile(self) -> None:
        selezionato = self.isChecked()
        bordo = self._colore if selezionato else _BORDO_INATTIVO
        sfondo = self._colore_bg if selezionato else "#FFFFFF"
        testo = self._colore if selezionato else _TESTO_INATTIVO
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {sfondo};
                border: 1.5px solid {bordo};
                border-radius: {TOGGLE_RADIUS}px;
            }}
            """
        )
        self._text_label.setStyleSheet(f"color: {testo}; background: transparent;")
        self._icon_label.setPixmap(load_lucide_icon(self._icona_nome, self._colore, 16).pixmap(16, 16))


class _EsitoToggle(QWidget):
    """Coppia Completato/Fallito, mutuamente esclusiva, nessuno selezionato all'apertura
    (l'utente deve scegliere attivamente - non c'e' un default ovvio nel mockup)."""

    esitoChanged = Signal(object)  # StatoEsito | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TOGGLE_GAP)

        self._btn_completato = _BottoneEsito("Completato", "circle-check-big", _VERDE_TESTO, _VERDE_BG, self)
        self._btn_fallito = _BottoneEsito("Fallito", "x", _ROSSO_TESTO, _ROSSO_BG, self)
        layout.addWidget(self._btn_completato, 1)
        layout.addWidget(self._btn_fallito, 1)

        self._btn_completato.clicked.connect(lambda: self._seleziona(StatoEsito.COMPLETATO))
        self._btn_fallito.clicked.connect(lambda: self._seleziona(StatoEsito.FALLITO))

    def _seleziona(self, esito: StatoEsito) -> None:
        self._btn_completato.setChecked(esito == StatoEsito.COMPLETATO)
        self._btn_fallito.setChecked(esito == StatoEsito.FALLITO)
        self.esitoChanged.emit(esito)

    def value(self) -> StatoEsito | None:
        if self._btn_completato.isChecked():
            return StatoEsito.COMPLETATO
        if self._btn_fallito.isChecked():
            return StatoEsito.FALLITO
        return None


def _sottotitolo_riga(riga: dict) -> str:
    parti = [riga.get("indirizzo") or "", riga.get("peso_volume") or ""]
    return "  ·  ".join(p for p in parti if p)


class RegistraEsitoModal(Modal):
    """RF16 (registra Completato/Fallito) + RF18 (almeno una prova documentale obbligatoria se
    Fallito, altre facoltative - la molteplicita' e l'obbligatorieta' sono validate solo qui lato
    GUI: carica_prova_documentale/registra_esito restano disaccoppiati per file, senza vincolo
    di "almeno uno" a livello di backend). RF17 (ripianificazione automatica) e' gia' interamente
    lato backend in GestoreRendicontazione.registra_esito(), qui solo la nota informativa."""

    esitoRegistrato = Signal()

    def __init__(
        self,
        riga: dict,
        gestore: GestoreRendicontazione,
        esito_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """`esito_id` assente (default) -> modalita' "registra" su un ordine in transito
        (chiamata registra_esito). `esito_id` valorizzato -> modalita' "modifica" su un esito
        gia' registrato (chiamata modifica_esito): `riga` deve avere in piu' le chiavi `esito`
        (label corrente, "Completato"/"Fallito") e `causale_codice` (None se Completato).

        Se si sta modificando un esito gia' Fallito (icona "occhio" sulla tab Esiti, non
        "matita"), la vista si riduce a sola visualizzazione di causale + prove gia' allegate:
        niente toggle Completato/Fallito (l'esito e' gia' un dato di fatto) e niente dropzone
        (non si possono aggiungere altre prove da qui - solo da un nuovo Fallito registrato via
        matita su Ordini o via matita su un esito ancora Completato)."""
        self._riga = riga
        self._gestore = gestore
        self._esito_id = esito_id
        self._allegati_esistenti: list[AllegatoVista] = []
        self._percorsi_prova_nuovi: list[Path] = []
        self._solo_causale_e_allegati = esito_id is not None and riga.get("esito") == "Fallito"

        # Occhio (sola visualizzazione): "Chiudi" al posto di "Annulla" (non c'e' nulla da
        # annullare) e nessun bottone "Salva" nel footer (nulla da salvare).
        self._btn_annulla = Button(
            ButtonVariant.SECONDARY, "Chiudi" if self._solo_causale_e_allegati else "Annulla"
        )
        etichetta_salva = "Salva modifiche" if esito_id is not None else "Salva esito"
        self._btn_salva = Button(ButtonVariant.PRIMARY, etichetta_salva)
        self._btn_salva.setEnabled(False)

        footer_buttons = [self._btn_annulla]
        if not self._solo_causale_e_allegati:
            footer_buttons.append(self._btn_salva)

        titolo = "Modifica esito consegna" if esito_id is not None else "Registra esito consegna"
        super().__init__(
            titolo,
            footer_buttons=footer_buttons,
            parent=parent,
        )

        self._btn_annulla.clicked.connect(self.close)
        self._btn_salva.clicked.connect(self._on_salva)

        self._toasts = ToastManager(self)

        self._costruisci_contenuto()
        if esito_id is not None:
            self._precompila_per_modifica()

    def _costruisci_contenuto(self) -> None:
        intestazione = QLabel(f"#{self._riga['id']}  ·  {self._riga['cliente']}")
        font = QFont("Inter")
        font.setWeight(QFont.Weight(600))
        font.setPixelSize(15)
        intestazione.setFont(font)
        intestazione.setStyleSheet("color: #2E2E2E;")
        self.add_widget(intestazione)

        sottotitolo = QLabel(_sottotitolo_riga(self._riga))
        font = QFont("Inter")
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(13)
        sottotitolo.setFont(font)
        sottotitolo.setStyleSheet(f"color: {_SUBTITLE_COLOR};")
        self.add_widget(sottotitolo)

        self._etichetta_esito = QLabel("Esito")
        self._etichetta_esito.setStyleSheet(f"color: {_SUBTITLE_COLOR}; margin-top: 8px;")
        self.add_widget(self._etichetta_esito)

        self._toggle = _EsitoToggle()
        self._toggle.esitoChanged.connect(self._on_esito_cambiato)
        self.add_widget(self._toggle)

        opzioni_causali = self._gestore.elenco_causali_fallimento()
        self._causale_per_descrizione = {descrizione: codice for codice, descrizione in opzioni_causali}
        self._select_causale = Select(
            "Causale del fallimento",
            options=list(self._causale_per_descrizione.keys()),
            placeholder="Seleziona una causale",
        )
        self._select_causale.valueChanged.connect(lambda _: self._aggiorna_salva_abilitato())
        self._select_causale.setVisible(False)
        self.add_widget(self._select_causale)

        etichetta_prove = QLabel("Prove allegate  ·  almeno una obbligatoria")
        etichetta_prove.setStyleSheet(f"color: {_SUBTITLE_COLOR};")
        self._etichetta_prove = etichetta_prove
        etichetta_prove.setVisible(False)
        self.add_widget(etichetta_prove)

        self._dropzone = Dropzone(
            heading="Trascina qui la prova o clicca per selezionare",
            dialog_title="Seleziona prova documentale",
        )
        self._dropzone.fileSelected.connect(self._on_prova_selezionata)
        self._dropzone.setVisible(False)
        self.add_widget(self._dropzone)

        self._lista_prove_widget = QWidget()
        self._lista_prove_layout = QVBoxLayout(self._lista_prove_widget)
        self._lista_prove_layout.setContentsMargins(0, 0, 0, 0)
        self._lista_prove_layout.setSpacing(6)
        self._lista_prove_widget.setVisible(False)
        self.add_widget(self._lista_prove_widget)

        self._nota_ripianificazione = QLabel(
            "ℹ  Questo ordine tornerà automaticamente in coda da pianificare"
        )
        self._nota_ripianificazione.setStyleSheet(f"color: {_INFO_COLOR}; font-size: 12px; margin-top: 4px;")
        self._nota_ripianificazione.setVisible(False)
        self.add_widget(self._nota_ripianificazione)

    def _crea_chip_prova(self, nome_file: str, rimuovibile: bool) -> QWidget:
        """`rimuovibile=False` per una prova gia' persistita (mostrata solo per informazione,
        in modalita' modifica) - non esiste un'operazione per eliminare un singolo Allegato gia'
        salvato, solo per aggiungerne altri."""
        chip = QWidget()
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        chip.setStyleSheet("background-color: #F7F9FC; border-radius: 8px;")

        etichetta = QLabel(nome_file)
        etichetta.setStyleSheet("background: transparent; color: #2E2E2E;")
        layout.addWidget(etichetta)
        layout.addStretch(1)

        if rimuovibile:
            rimuovi = Button(ButtonVariant.ICON_ONLY, icon=load_lucide_icon("x", "#5B6472", 13))
            rimuovi.clicked.connect(lambda: self._rimuovi_prova_nuova(nome_file))
            layout.addWidget(rimuovi)
        else:
            gia_caricata = QLabel("già caricata")
            gia_caricata.setStyleSheet(f"background: transparent; color: {_SUBTITLE_COLOR}; font-size: 11px;")
            layout.addWidget(gia_caricata)
        return chip

    def _ricostruisci_lista_prove(self) -> None:
        while self._lista_prove_layout.count():
            item = self._lista_prove_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        for allegato in self._allegati_esistenti:
            self._lista_prove_layout.addWidget(self._crea_chip_prova(allegato.nome_file, rimuovibile=False))
        for percorso in self._percorsi_prova_nuovi:
            self._lista_prove_layout.addWidget(self._crea_chip_prova(percorso.name, rimuovibile=True))

        self._lista_prove_widget.setVisible(
            bool(self._allegati_esistenti) or bool(self._percorsi_prova_nuovi)
        )

    def _on_esito_cambiato(self, esito: StatoEsito) -> None:
        fallito = esito == StatoEsito.FALLITO
        self._select_causale.setVisible(fallito)
        self._etichetta_prove.setVisible(fallito)
        self._dropzone.setVisible(fallito)
        self._lista_prove_widget.setVisible(
            fallito and (bool(self._allegati_esistenti) or bool(self._percorsi_prova_nuovi))
        )
        self._nota_ripianificazione.setVisible(fallito)
        if not fallito:
            self._select_causale.set_value(None)
        self._aggiorna_salva_abilitato()

    def _on_prova_selezionata(self, percorso: Path) -> None:
        if self._solo_causale_e_allegati:
            # Difensivo: la dropzone e' nascosta in questa modalita' e non dovrebbe mai emettere,
            # ma se lo facesse comunque (es. drag&drop diretto sul widget) non deve aggiungere -
            # sola visualizzazione, invariante indipendente dalla sola visibilita' del widget.
            return
        self._percorsi_prova_nuovi.append(percorso)
        self._ricostruisci_lista_prove()
        self._aggiorna_salva_abilitato()

    def _rimuovi_prova_nuova(self, nome_file: str) -> None:
        for percorso in list(self._percorsi_prova_nuovi):
            if percorso.name == nome_file:
                self._percorsi_prova_nuovi.remove(percorso)
                break
        self._ricostruisci_lista_prove()
        self._aggiorna_salva_abilitato()

    def _numero_prove_totali(self) -> int:
        return len(self._allegati_esistenti) + len(self._percorsi_prova_nuovi)

    def _aggiorna_salva_abilitato(self) -> None:
        esito = self._toggle.value()
        if esito == StatoEsito.COMPLETATO:
            self._btn_salva.setEnabled(True)
        elif esito == StatoEsito.FALLITO:
            # RF18: almeno una prova documentale e' obbligatoria per un esito Fallito, sia in
            # registrazione sia in modifica.
            self._btn_salva.setEnabled(bool(self._select_causale.value()) and self._numero_prove_totali() > 0)
        else:
            self._btn_salva.setEnabled(False)

    def _on_salva(self) -> None:
        esito = self._toggle.value()
        if esito is None:
            return
        causale_codice = None
        if esito == StatoEsito.FALLITO:
            descrizione = self._select_causale.value()
            causale_codice = self._causale_per_descrizione.get(descrizione) if descrizione else None

        if self._esito_id is not None:
            risultato = self._gestore.modifica_esito(self._esito_id, esito, causale_codice)
            esito_id_per_prova = self._esito_id
            messaggio_errore = "Impossibile modificare l'esito"
        else:
            risultato = self._gestore.registra_esito(self._riga["id"], esito, causale_codice)
            esito_id_per_prova = risultato.esito_id
            messaggio_errore = "Impossibile registrare l'esito"

        if not risultato.ok:
            self._toasts.show_error(messaggio_errore, risultato.motivo or "Operazione rifiutata.")
            return

        if esito == StatoEsito.FALLITO:
            for percorso in self._percorsi_prova_nuovi:
                tipo_file = mimetypes.guess_type(percorso.name)[0] or "application/octet-stream"
                self._gestore.carica_prova_documentale(
                    esito_id_per_prova, percorso.name, str(percorso), tipo_file
                )

        self.close()
        self.esitoRegistrato.emit()

    def _precompila_per_modifica(self) -> None:
        esito_corrente = StatoEsito(self._riga["esito"])
        if esito_corrente == StatoEsito.FALLITO:
            self._allegati_esistenti = self._gestore.elenco_allegati(self._esito_id)
        self._toggle._seleziona(esito_corrente)
        causale_codice = self._riga.get("causale_codice")
        if causale_codice is not None:
            descrizione = next(
                (desc for desc, cod in self._causale_per_descrizione.items() if cod == causale_codice), None
            )
            if descrizione is not None:
                self._select_causale.set_value(descrizione)
        self._ricostruisci_lista_prove()
        self._aggiorna_salva_abilitato()

        if self._solo_causale_e_allegati:
            self._etichetta_esito.setVisible(False)
            self._toggle.setVisible(False)
            self._nota_ripianificazione.setVisible(False)
            # Sola visualizzazione delle prove gia' caricate: niente dropzone, non si possono
            # aggiungerne altre da qui (solo da un nuovo Fallito registrato via matita/Ordini).
            self._dropzone.setVisible(False)
            self._etichetta_prove.setText("Prove allegate")
            # Coerenza col footer senza "Salva": la causale resta visibile (serve a capire il
            # motivo del fallimento) ma non modificabile, non ci sarebbe modo di salvare la
            # modifica da questa card.
            self._select_causale.setEnabled(False)
