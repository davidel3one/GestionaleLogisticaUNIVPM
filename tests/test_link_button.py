"""Regressione GUI per il componente LinkButton (testo cliccabile in stile link).

Nessun pytest-qt nel progetto: si usa QTest con la piattaforma "offscreen" e una singola
QApplication a livello di modulo, stesso pattern di test_form_field.py/test_modal.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from gestionale_logistica.gui.components.link_button import LINK_COLOR, LinkButton


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def test_testo_mostrato(app):
    link = LinkButton("Invia di nuovo")
    assert link.text() == "Invia di nuovo"


def test_colore_di_riposo(app):
    link = LinkButton("Invia di nuovo")
    assert LINK_COLOR in link.styleSheet()


def test_click_emette_clicked(app):
    link = LinkButton("Invia di nuovo")
    click_avvenuto = []
    link.clicked.connect(lambda: click_avvenuto.append(True))
    QTest.mouseClick(link, Qt.MouseButton.LeftButton)
    assert click_avvenuto == [True]
