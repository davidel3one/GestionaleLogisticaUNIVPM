"""Componente Card riusabile, container con chrome base condivisa (fonte: mockup Sketch, gui-design.sketch)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


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
