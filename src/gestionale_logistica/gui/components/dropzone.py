"""Dropzone: click apre un file picker, drag&drop accetta un file rilasciato (fonte: mockup
Sketch, riquadro tratteggiato "Trascina qui... o clicca per selezionare", ripetuto identico
nei modali "Importa CSV" e "Registra esito consegna" - estratto da `ImportCsvModal` come
componente riusabile invece di duplicare la logica drag&drop in ogni modale che carica un file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout, QWidget

from gestionale_logistica.gui.components.icons import load_lucide_icon

_DROPZONE_BG = "#FAFBFD"
_DROPZONE_BORDER = "#D6DEE8"
_DROPZONE_TEXT_COLOR = "#2E2E2E"
_DROPZONE_ICON_COLOR = "#3D9BE9"


class Dropzone(QFrame):
    fileSelected = Signal(Path)

    def __init__(
        self,
        heading: str = "Trascina qui il file o clicca per selezionarlo",
        file_filter: str = "Tutti i file (*)",
        dialog_title: str = "Seleziona file",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter
        self._dialog_title = dialog_title

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(150)
        self.setStyleSheet(
            f"""
            Dropzone {{
                background-color: {_DROPZONE_BG};
                border: 1.5px solid {_DROPZONE_BORDER};
                border-radius: 8px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon_label = QLabel(self)
        icon_label.setPixmap(load_lucide_icon("upload", _DROPZONE_ICON_COLOR, 36).pixmap(QSize(36, 36)))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        self._heading = QLabel(heading, self)
        self._heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Inter")
        font.setWeight(QFont.Weight(500))
        font.setPixelSize(13)
        self._heading.setFont(font)
        self._heading.setStyleSheet(f"color: {_DROPZONE_TEXT_COLOR}; background: transparent;")
        layout.addWidget(self._heading)

    def mousePressEvent(self, event) -> None:  # noqa: ARG002 (firma richiesta da Qt)
        percorso = self._sfoglia()
        if percorso is not None:
            self._imposta_selezionato(percorso)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            self._imposta_selezionato(Path(urls[0].toLocalFile()))

    def _sfoglia(self) -> Path | None:
        percorso, _ = QFileDialog.getOpenFileName(self, self._dialog_title, "", self._file_filter)
        return Path(percorso) if percorso else None

    def _imposta_selezionato(self, percorso: Path) -> None:
        self._heading.setText(percorso.name)
        self.fileSelected.emit(percorso)
