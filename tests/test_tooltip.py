"""Regressione GUI per il componente Tooltip (hover mostra/nasconde il popover).

Nessun pytest-qt nel progetto: si usa una singola QApplication a livello di modulo con
piattaforma "offscreen", stesso pattern di test_modal.py/test_form_field.py. L'hover reale
via QTest.mouseMove non è affidabile in offscreen (nessun tracking del cursore a livello
OS): si chiamano direttamente `show_popover()`/`hide_popover()`, la stessa logica invocata
da `enterEvent`/`leaveEvent`.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.components.tooltip import Tooltip


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_tooltip_popover_nascosto_inizialmente(app):
    tip = Tooltip("Spiegazione RNF4")
    assert not tip._popover.isVisible()


def test_tooltip_show_popover_lo_rende_visibile_con_testo_corretto(app):
    tip = Tooltip("Spiegazione RNF4")
    tip.show_popover()
    assert tip._popover.isVisible()
    assert tip._popover.text() == "Spiegazione RNF4"


def test_tooltip_hide_popover_lo_nasconde(app):
    tip = Tooltip("Spiegazione RNF4")
    tip.show_popover()
    tip.hide_popover()
    assert not tip._popover.isVisible()


def test_tooltip_enter_event_mostra_popover(app):
    tip = Tooltip("Spiegazione RNF4")
    tip.enterEvent(None)
    assert tip._popover.isVisible()


def test_tooltip_leave_event_nasconde_popover(app):
    tip = Tooltip("Spiegazione RNF4")
    tip.enterEvent(None)
    tip.leaveEvent(None)
    assert not tip._popover.isVisible()


def test_tooltip_icona_dimensione_18x18(app):
    tip = Tooltip("Spiegazione RNF4")
    assert tip.size().width() == 18
    assert tip.size().height() == 18
