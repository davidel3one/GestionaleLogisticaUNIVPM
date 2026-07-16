"""Componente Card riusabile, container con chrome base condivisa (fonte: mockup Sketch, gui-design.sketch)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget


class Card(QFrame):
    """Container riusabile: sfondo bianco, bordo arrotondato, layout verticale di default."""

    def __init__(
        self,
        padding_horizontal: int = 24,
        padding_vertical: int = 20,
        spacing: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Fix (2026-07-15): stesso motivo di PageHeader (vedi page_header.py) - senza questo, in
        # un QVBoxLayout con poco contenuto sotto (es. Table con poche righe) la Filter Card si
        # allarga verticalmente per riempire lo spazio residuo invece di restare alla sua altezza
        # naturale. Le uniche istanze di Card in uso oggi (Filter Card) hanno sempre altezza
        # dettata dal contenuto nel mockup - se in futuro serve una Card che deve espandersi
        # (es. un contenitore a tutta altezza), va esposto come parametro, non assunto di default.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(
            padding_horizontal, padding_vertical, padding_horizontal, padding_vertical
        )
        self.content_layout.setSpacing(spacing)

        self._apply_style()

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            Card {
                background-color: #FFFFFF;
                border: 1px solid #E5EAF0;
                border-radius: 14px;
            }
            """
        )
