"""Regressione GUI per il componente Modal (click backdrop vs click dentro la card).

Nessun pytest-qt nel progetto: si usa QTest con la piattaforma "offscreen" e una singola
QApplication a livello di modulo, così i test girano headless come il resto della suite.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from gestionale_logistica.gui.components.button import Button, ButtonVariant
from gestionale_logistica.gui.components.modal import Modal


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def host(app):
    widget = QWidget()
    widget.resize(1000, 700)
    widget.show()
    yield widget
    widget.deleteLater()


def _open_modal(host: QWidget) -> Modal:
    modal = Modal(
        "Titolo",
        "Sottotitolo",
        width=560,
        footer_buttons=[Button(ButtonVariant.PRIMARY, text="OK")],
    )
    modal.add_widget(QWidget())
    modal.show_over(host)
    QApplication.processEvents()
    return modal


def _click(widget: QWidget) -> None:
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=widget.rect().center())
    QApplication.processEvents()


def test_click_dentro_la_card_non_chiude(host):
    modal = _open_modal(host)
    _click(modal._card)
    assert modal.isVisible()


def test_click_su_header_e_content_non_chiude(host):
    modal = _open_modal(host)
    header = modal._card.layout().itemAt(0).widget()
    content = modal._card.layout().itemAt(2).widget()
    _click(header)
    assert modal.isVisible()
    _click(content)
    assert modal.isVisible()


def test_click_sul_backdrop_chiude(host):
    modal = _open_modal(host)
    QTest.mouseClick(modal, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QApplication.processEvents()
    assert not modal.isVisible()


def test_esc_chiude(host):
    modal = _open_modal(host)
    QTest.keyClick(modal, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert not modal.isVisible()
