"""Evidenziazione (numero del giorno in azzurro, non piu' sfondo del tassello) dei giorni con
almeno una composizione squadra attiva disponibile, sul popup calendario di Pianificazione
(Automatica/Manuale/Assistita) - stessa condizione gia' usata dall'hint "N composizioni attive
disponibili per il ..." (vedi `pianificazione_data.giorni_con_composizioni_disponibili`).

Richiesta esplicita dell'utente (2026-07-16): non piu' il tassello colorato (sfondo verde), solo
il numero in azzurro - riuso di `AZZURRO`/`IconChipVariant.LIGHT_BLUE` (`#3D9BE9`), la stessa
tinta azzurra gia' usata altrove in Pianificazione (KPI "Viaggi proposti"/"Ordini assegnati" in
`automatica_tab.py`), non un colore nuovo."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.gui.components.icon_chip import IconChipVariant, VARIANT_COLORS
from gestionale_logistica.gui.pages.pianificazione.pianificazione_data import (
    giorni_con_composizioni_disponibili,
)

# Nessuno sfondo impostato: senza un tassello colorato a fare contrasto non serve piu'
# sovrascrivere il rosso nativo di Qt sui weekend (vedi versione precedente di questo file) -
# l'azzurro sostituisce il colore del testo per ogni giorno marcato, weekend incluso, la stessa
# unica indicazione visiva che prima dava lo sfondo.
_AZZURRO = QColor(VARIANT_COLORS[IconChipVariant.LIGHT_BLUE][0])


def evidenzia_giorni_con_squadre_attive(
    calendar: QCalendarWidget, session_factory: sessionmaker = SessionLocal
) -> None:
    """Colora in azzurro, ad ogni cambio del mese visualizzato nel popup, il numero dei giorni
    con almeno una composizione attiva disponibile in quel giorno. `setDateTextFormat` è
    per-data assoluta (non per pagina visualizzata): niente da "ripulire" quando si cambia
    mese, ogni giorno tiene il proprio formato indipendentemente da quale mese è in vista."""

    def _aggiorna(anno: int, mese: int) -> None:
        for giorno in giorni_con_composizioni_disponibili(date(anno, mese, 1), session_factory):
            qdate = QDate(giorno.year, giorno.month, giorno.day)
            formato = QTextCharFormat()
            formato.setForeground(_AZZURRO)
            calendar.setDateTextFormat(qdate, formato)

    calendar.currentPageChanged.connect(_aggiorna)
    oggi = calendar.selectedDate()
    _aggiorna(oggi.year(), oggi.month())
