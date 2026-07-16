"""DettaglioViaggioPropostoModal: modale read-only aperto dal chevron "espandi riga" della
Proposed Trips Table (Pianificazione — Automatica, RF13). Nessun artboard dedicato nel mockup per
questa affordance (era segnalato "nessun comportamento/modale specificato" in automatica_tab.py);
stile allineato al modale "Squadre — Dettaglio" del mockup per coerenza con l'app esistente
(Modal width=900, nessun footer, tabella ordini read-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from gestionale_logistica.gui.components import ColumnDef, ColumnType, Modal, Table, TextEmphasis
from gestionale_logistica.gui.pianificazione.components.composition_card import CATEGORIA_BADGE_COLORS

if TYPE_CHECKING:
    # Import solo per type-checking: a runtime creerebbe un ciclo, dato che pianificazione_data
    # importa a sua volta il package `components` (di cui questo modulo fa parte).
    from gestionale_logistica.gui.pianificazione.pianificazione_data import DettaglioViaggioProposto

_TABLE_COLUMNS = [
    ColumnDef(key="cliente", label="Cliente", stretch=2),
    ColumnDef(key="peso", label="Peso", emphasis=TextEmphasis.SECONDARY, stretch=1),
    ColumnDef(key="volume", label="Volume", emphasis=TextEmphasis.SECONDARY, stretch=1),
    ColumnDef(
        key="categoria",
        label="Categoria",
        column_type=ColumnType.STATUS_BADGE,
        status_colors=CATEGORIA_BADGE_COLORS,
        width=140,
    ),
]


class DettaglioViaggioPropostoModal(Modal):
    def __init__(self, dettaglio: DettaglioViaggioProposto, parent: QWidget | None = None) -> None:
        super().__init__(
            f"Squadra {dettaglio.squadra_label}",
            subtitle=f"{dettaglio.camion_label}  ·  {dettaglio.partenza_label} → {dettaglio.arrivo_label}",
            width=900,
            parent=parent,
        )
        table = Table(_TABLE_COLUMNS, show_footer=False)
        table.set_rows(
            [
                {
                    "cliente": riga.cliente,
                    "peso": f"{riga.peso:g} kg",
                    "volume": f"{riga.volume:g} m³",
                    "categoria": riga.categoria_label,
                }
                for riga in dettaglio.righe_ordini
            ]
        )
        self.add_widget(table)
