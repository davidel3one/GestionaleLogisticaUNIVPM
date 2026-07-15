"""Regressione GUI per i campi di input di un form: TextField, Select, BooleanToggle,
DatePicker, MultiSelect.

Nessun pytest-qt nel progetto: si usa QTest con la piattaforma "offscreen" e una singola
QApplication a livello di modulo, così i test girano headless come il resto della suite
(stesso pattern di test_modal.py).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.components.form_field import (
    DATE_FORMAT,
    BooleanToggle,
    DatePicker,
    MultiSelect,
    Select,
    TextField,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


# --- TextField ---------------------------------------------------------------------


def test_text_field_value_iniziale_vuoto(app):
    field = TextField("Capacità (kg)", placeholder="es. 1200")
    assert field.value() == ""


def test_text_field_set_value(app):
    field = TextField("Capacità (kg)", placeholder="es. 1200")
    field.set_value("1200")
    assert field.value() == "1200"


def test_text_field_digitazione_emette_value_changed(app):
    field = TextField("Targa", placeholder="es. AB123CD")
    ricevuti = []
    field.valueChanged.connect(ricevuti.append)
    QTest.keyClicks(field._input, "AB123CD")
    assert field.value() == "AB123CD"
    assert ricevuti[-1] == "AB123CD"


# --- Select --------------------------------------------------------------------------


def test_select_value_iniziale_none(app):
    select = Select("Tipo mezzo", options=["Furgone", "Camion"], placeholder="Seleziona")
    assert select.value() is None
    assert select._box.text_label.text() == "Seleziona"


def test_select_set_value_aggiorna_testo_e_valore(app):
    select = Select("Tipo mezzo", options=["Furgone", "Camion"], placeholder="Seleziona")
    select.set_value("Camion")
    assert select.value() == "Camion"
    assert select._box.text_label.text() == "Camion"


def test_select_menu_contiene_tutte_le_opzioni(app):
    opzioni = ["Furgone", "Camion", "Bilico"]
    select = Select("Tipo mezzo", options=opzioni, placeholder="Seleziona")
    menu = select._build_menu()
    assert [azione.text() for azione in menu.actions()] == opzioni


def test_select_scegliere_una_voce_del_menu_emette_value_changed(app):
    select = Select("Tipo mezzo", options=["Furgone", "Camion"], placeholder="Seleziona")
    ricevuti = []
    select.valueChanged.connect(ricevuti.append)
    menu = select._build_menu()
    menu.actions()[1].trigger()
    assert select.value() == "Camion"
    assert ricevuti == ["Camion"]


def test_select_box_sizehint_non_tronca_il_contenuto(app):
    select = Select("Stato", options=["Attivo", "In viaggio", "Cessato"], placeholder="Cessato")
    assert select._box.sizeHint() == select._box.layout().sizeHint()
    assert select._box.sizeHint().width() >= select._box.text_label.sizeHint().width()


# --- BooleanToggle ---------------------------------------------------------------------


def test_boolean_toggle_default_no(app):
    toggle = BooleanToggle("Sponda idraulica")
    assert toggle.value() is False


def test_boolean_toggle_click_su_si_seleziona_si(app):
    toggle = BooleanToggle("Sponda idraulica")
    QTest.mouseClick(toggle._yes_pill, Qt.MouseButton.LeftButton)
    assert toggle.value() is True


def test_boolean_toggle_set_value_aggiorna_stato(app):
    toggle = BooleanToggle("Certificazione gas")
    ricevuti = []
    toggle.valueChanged.connect(ricevuti.append)
    toggle.set_value(True)
    assert toggle.value() is True
    assert ricevuti == [True]
    toggle.set_value(False)
    assert toggle.value() is False
    assert ricevuti == [True, False]


# --- DatePicker ---------------------------------------------------------------------


def test_date_picker_formato_gg_mm_aaaa(app):
    field = DatePicker("Data consegna")
    assert field._input.displayFormat() == DATE_FORMAT


def test_date_picker_set_value_e_value(app):
    field = DatePicker("Data consegna")
    data = QDate(2026, 7, 11)
    field.set_value(data)
    assert field.value() == data


def test_date_picker_cambio_data_emette_value_changed(app):
    field = DatePicker("Data consegna")
    ricevuti = []
    field.valueChanged.connect(ricevuti.append)
    nuova_data = QDate(2020, 10, 14)
    field.set_value(nuova_data)
    assert ricevuti == [nuova_data]


# --- MultiSelect ---------------------------------------------------------------------


def test_multi_select_value_iniziale_vuoto_mostra_placeholder(app):
    campo = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer"], placeholder="Seleziona...")
    assert campo.value() == []
    assert campo._box.text_label.text() == "Seleziona..."


def test_multi_select_set_value_aggiorna_testo_riassuntivo(app):
    campo = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer"])
    campo.set_value(["Lun", "Mer"])
    assert campo.value() == ["Lun", "Mer"]
    assert campo._box.text_label.text() == "2 selezionati"


def test_multi_select_set_value_una_sola_opzione_mostra_il_nome(app):
    campo = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer"])
    campo.set_value(["Mar"])
    assert campo._box.text_label.text() == "Mar"


def test_multi_select_menu_contiene_una_checkbox_per_opzione(app):
    opzioni = ["Lun", "Mar", "Mer"]
    campo = MultiSelect("Giorni disponibili", options=opzioni)
    menu = campo._build_menu()
    checkbox_texts = [azione.defaultWidget().text() for azione in menu.actions()]
    assert checkbox_texts == opzioni


def test_multi_select_selezionare_checkbox_emette_value_changed(app):
    campo = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer"])
    ricevuti = []
    campo.valueChanged.connect(ricevuti.append)
    menu = campo._build_menu()
    menu.actions()[0].defaultWidget().setChecked(True)
    assert campo.value() == ["Lun"]
    assert ricevuti == [["Lun"]]


def test_multi_select_deselezionare_checkbox_rimuove_il_valore(app):
    campo = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer"])
    campo.set_value(["Lun", "Mar"])
    menu = campo._build_menu()
    menu.actions()[0].defaultWidget().setChecked(False)
    assert campo.value() == ["Mar"]
