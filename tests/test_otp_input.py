"""Regressione GUI per il componente OtpInput (6 caselle codice conferma).

Nessun pytest-qt nel progetto: si usa QTest con la piattaforma "offscreen" e una singola
QApplication a livello di modulo, stesso pattern di test_form_field.py/test_modal.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, Qt
from PySide6.QtTest import QTest

from gestionale_logistica.gui.components.otp_input import OtpInput


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def test_value_vuoto_inizialmente(app):
    otp = OtpInput()
    assert otp.value() == ""


def test_digitazione_avanza_alla_casella_successiva(app):
    otp = OtpInput()
    otp.show()
    QTest.qWaitForWindowExposed(otp)
    otp.activateWindow()
    QTest.keyClicks(otp._boxes[0], "4")
    assert otp._boxes[0].text() == "4"
    assert otp._boxes[1].hasFocus()


def test_value_concatena_le_caselle(app):
    otp = OtpInput()
    for i, cifra in enumerate("42"):
        otp._boxes[i].setText(cifra)
    assert otp.value() == "42"


def test_set_value_popola_le_caselle(app):
    otp = OtpInput()
    otp.set_value("123456")
    assert otp.value() == "123456"


def test_set_value_ignora_caratteri_non_numerici(app):
    otp = OtpInput()
    otp.set_value("1a2b3c")
    assert otp.value() == "123"


def test_backspace_su_casella_vuota_torna_alla_precedente(app):
    otp = OtpInput()
    otp.show()
    QTest.qWaitForWindowExposed(otp)
    otp.activateWindow()
    otp._boxes[1].setFocus()
    QTest.keyClick(otp._boxes[1], Qt.Key.Key_Backspace)
    assert otp._boxes[0].hasFocus()


def test_carattere_non_numerico_viene_scartato(app):
    otp = OtpInput()
    QTest.keyClicks(otp._boxes[0], "a")
    assert otp._boxes[0].text() == ""


def test_incolla_multi_cifra_distribuisce_sulle_caselle_successive(app):
    otp = OtpInput()
    mime = QMimeData()
    mime.setText("123456")
    otp._boxes[0].insertFromMimeData(mime)
    assert otp.value() == "123456"


def test_valuechanged_emesso_alla_digitazione(app):
    otp = OtpInput()
    valori = []
    otp.valueChanged.connect(valori.append)
    QTest.keyClicks(otp._boxes[0], "4")
    assert valori[-1] == "4"


def test_clear_svuota_e_focalizza_la_prima_casella(app):
    otp = OtpInput()
    otp.show()
    QTest.qWaitForWindowExposed(otp)
    otp.activateWindow()
    otp.set_value("123456")
    otp.clear()
    assert otp.value() == ""
    assert otp._boxes[0].hasFocus()
