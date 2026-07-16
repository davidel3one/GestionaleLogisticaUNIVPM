"""Pagina Pianificazione: 3 modalità (RF13 Automatica, RF12 Assistita, RF10/RF11 Manuale) dietro
una TabBar (fonte: mockup Sketch, artboard "Pianificazione" / "— Assistita" / "— Manuale")."""

from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components import PageHeader, TabBar
from gestionale_logistica.gui.pianificazione.assistita_tab import AssistitaTab
from gestionale_logistica.gui.pianificazione.automatica_tab import AutomaticaTab
from gestionale_logistica.gui.pianificazione.manuale_tab import ManualeTab

CONTENT_PADDING = 32
CONTENT_GAP = 28

TAB_LABELS = ["Automatica", "Assistita", "Manuale"]


class PianificazionePage(QWidget):
    def __init__(self, session_factory: sessionmaker = SessionLocal, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING)
        outer.setSpacing(CONTENT_GAP)

        outer.addWidget(PageHeader("Pianificazione"))

        self._tab_bar = TabBar(TAB_LABELS)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self._tab_bar)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        self._stack.addWidget(AutomaticaTab(session_factory))
        self._stack.addWidget(AssistitaTab(session_factory))
        self._stack.addWidget(ManualeTab(session_factory))

    def _on_tab_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
