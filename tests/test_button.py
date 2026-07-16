"""Regressione GUI per il componente Button (5 varianti).

Nessun pytest-qt nel progetto: si usa QTest con la piattaforma "offscreen" e una singola
QApplication a livello di modulo, stesso pattern di test_link_button.py/test_form_field.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt

from gestionale_logistica.gui.components.button import Button, ButtonVariant


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def test_click_emette_clicked(app):
    bottone = Button(ButtonVariant.PRIMARY, "Conferma")
    click_avvenuto = []
    bottone.clicked.connect(lambda: click_avvenuto.append(True))

    from PySide6.QtTest import QTest

    QTest.mouseClick(bottone, Qt.MouseButton.LeftButton)
    assert click_avvenuto == [True]


def test_icon_only_richiede_icona(app):
    with pytest.raises(ValueError):
        Button(ButtonVariant.ICON_ONLY)


def test_secondary_header_add_richiede_icona(app):
    with pytest.raises(ValueError):
        Button(ButtonVariant.SECONDARY_HEADER_ADD, "Aggiungi")


def test_set_text_aggiorna_la_label_interna(app):
    bottone = Button(ButtonVariant.PRIMARY, "Chiudi viaggio")
    bottone.set_text("Applica suggerimento e chiudi viaggio")
    assert bottone._text_label_widget.text() == "Applica suggerimento e chiudi viaggio"


def test_disabled_riduce_opacita_e_cambia_cursore(app):
    bottone = Button(ButtonVariant.PRIMARY, "Conferma")
    bottone.setEnabled(False)
    assert bottone.graphicsEffect() is not None
    assert bottone.cursor().shape() == Qt.CursorShape.ArrowCursor

    bottone.setEnabled(True)
    assert bottone.graphicsEffect() is None
    assert bottone.cursor().shape() == Qt.CursorShape.PointingHandCursor
