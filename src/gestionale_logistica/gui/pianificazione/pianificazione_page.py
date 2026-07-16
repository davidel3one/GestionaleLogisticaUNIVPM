"""Pagina Pianificazione: 3 modalità (RF13 Automatica, RF12 Assistita, RF10/RF11 Manuale) dietro
una TabBar (fonte: mockup Sketch, artboard "Pianificazione" / "— Assistita" / "— Manuale")."""

from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import Button, ButtonVariant, PageHeader, TabBar, load_lucide_icon
from gestionale_logistica.gui.components.toast import ToastManager
from gestionale_logistica.gui.pianificazione.assistita_tab import AssistitaTab
from gestionale_logistica.gui.pianificazione.automatica_tab import AutomaticaTab
from gestionale_logistica.gui.pianificazione.components import ImpostazioniPianificazioneModal
from gestionale_logistica.gui.pianificazione.manuale_tab import ManualeTab
from gestionale_logistica.ottimizzazione.gestore_configurazione import GestoreConfigurazione

CONTENT_PADDING = 32
CONTENT_GAP = 28

TAB_LABELS = ["Automatica", "Assistita", "Manuale"]


class PianificazionePage(QWidget):
    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gestore_config = GestoreConfigurazione(session_factory)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING)
        outer.setSpacing(CONTENT_GAP)

        impostazioni_button = Button(
            ButtonVariant.ICON_ONLY, icon=load_lucide_icon("settings", "#2E2E2E", 15)
        )
        impostazioni_button.clicked.connect(self._apri_impostazioni)
        outer.addWidget(PageHeader("Pianificazione", [impostazioni_button]))

        self._tab_bar = TabBar(TAB_LABELS)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        automatica_tab = AutomaticaTab(session_factory)
        automatica_tab.pianoApplicato.connect(self._on_piano_applicato)
        self._stack.addWidget(automatica_tab)

        assistita_tab = AssistitaTab(session_factory)
        assistita_tab.viaggioChiuso.connect(self._on_viaggio_chiuso)
        self._stack.addWidget(assistita_tab)

        self._stack.addWidget(ManualeTab(session_factory))

        self._toasts = ToastManager(self)

    def mostra_tab_automatica(self) -> None:
        """Chiamato dalla Dashboard quando l'utente preme "Nuova pianificazione"."""
        self._tab_bar.set_current_index(0)

    def _on_tab_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _apri_impostazioni(self) -> None:
        self._impostazioni_modal = ImpostazioniPianificazioneModal(self, self._gestore_config)
        self._impostazioni_modal.show()

    def _on_piano_applicato(self, numero_viaggi: int) -> None:
        etichetta = "viaggio pianificato" if numero_viaggi == 1 else "viaggi pianificati"
        self._toasts.show_success(f"{numero_viaggi} {etichetta}")

    def _on_viaggio_chiuso(self) -> None:
        self._toasts.show_success("Viaggio aggiunto")
