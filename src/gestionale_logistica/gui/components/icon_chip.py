"""IconChip: tassello circolare colorato con un'icona Lucide dentro (fonte: mockup Sketch,
verificato su KPI Card e Activity Row della Dashboard)."""

from __future__ import annotations

import enum

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QWidget

from gestionale_logistica.gui.components.icons import load_lucide_icon


class IconChipVariant(enum.Enum):
    LIGHT_BLUE = "light_blue"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    AMBER = "amber"


# (colore icona, colore sfondo chip) per variante, misurati nel mockup Sketch.
VARIANT_COLORS: dict[IconChipVariant, tuple[str, str]] = {
    IconChipVariant.LIGHT_BLUE: ("#3D9BE9", "#D6EAFB"),
    IconChipVariant.BLUE: ("#2563C9", "#D6E4F7"),
    IconChipVariant.GREEN: ("#1E8E3E", "#DFF5E5"),
    IconChipVariant.RED: ("#C0392B", "#FBE4E1"),
    # AMBER (aggiunta 2026-07-16 per Toast): non e' una delle 4 combinazioni originarie
    # misurate su un'istanza IconChip del mockup, ma riusa 1:1 la coppia gia' misurata
    # altrove nello stesso mockup per lo stato ambra (STATUS_BADGE "In consegna",
    # CATEGORIA_BADGE "Big"/"Certificazione Gas") - nessun colore nuovo/estrapolato.
    IconChipVariant.AMBER: ("#B45309", "#FEF3C7"),
}


class IconChip(QLabel):
    """Chip circolare (16x16 nel mockup): icona Lucide colorata su uno sfondo tinta chiara della
    stessa famiglia di colore. Le 4 combinazioni icona/sfondo sono misurate nel mockup, non stimate."""

    def __init__(
        self,
        icon_name: str,
        variant: IconChipVariant,
        size: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        icon_color, bg_color = VARIANT_COLORS[variant]

        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
            IconChip {{
                background-color: {bg_color};
                border-radius: {size // 2}px;
            }}
            """
        )
        icon = load_lucide_icon(icon_name, icon_color, size)
        self.setPixmap(icon.pixmap(QSize(size, size)))
