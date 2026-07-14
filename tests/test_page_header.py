"""Regressione GUI per PageHeader, SearchField, EmptyState.

Stesso pattern headless del resto della suite (test_form_field.py): piattaforma Qt
"offscreen" e una singola QApplication a livello di modulo, senza pytest-qt.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.components import (
    Button,
    ButtonVariant,
    EmptyState,
    PageHeader,
    SearchField,
    load_lucide_icon,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


# --- PageHeader ----------------------------------------------------------------------


def test_page_header_solo_titolo(app):
    header = PageHeader("Squadre")
    assert header._title_label.text() == "Squadre"


def test_page_header_set_title(app):
    header = PageHeader("Ordini")
    header.set_title("Camion")
    assert header._title_label.text() == "Camion"


def test_page_header_con_azioni_le_aggiunge_al_layout(app):
    azione = Button(
        ButtonVariant.SECONDARY_HEADER_ADD,
        "Nuova squadra",
        load_lucide_icon("circle-plus", "#2E2E2E", 15),
    )
    header = PageHeader("Squadre", actions=[azione])
    assert azione.parent() is header


def test_page_header_senza_azioni_non_solleva(app):
    header = PageHeader("Dashboard", actions=None)
    assert header._title_label.text() == "Dashboard"


# --- SearchField ---------------------------------------------------------------------


def test_search_field_value_iniziale_vuoto(app):
    campo = SearchField()
    assert campo.value() == ""


def test_search_field_placeholder_default(app):
    campo = SearchField()
    assert campo._input.placeholderText() == "Cerca..."


def test_search_field_placeholder_custom(app):
    campo = SearchField(placeholder="Cerca dipendente, camion...")
    assert campo._input.placeholderText() == "Cerca dipendente, camion..."


def test_search_field_set_value(app):
    campo = SearchField()
    campo.set_value("Rossi")
    assert campo.value() == "Rossi"


def test_search_field_digitazione_emette_search_changed(app):
    campo = SearchField()
    ricevuti = []
    campo.searchChanged.connect(ricevuti.append)
    QTest.keyClicks(campo._input, "Rossi")
    assert campo.value() == "Rossi"
    assert ricevuti[-1] == "Rossi"


# --- EmptyState ----------------------------------------------------------------------


def test_empty_state_con_sottotitolo(app):
    stato = EmptyState("Nessuna squadra", "Le squadre che crei appariranno qui", "inbox")
    testi = _label_texts(stato)
    assert "Nessuna squadra" in testi
    assert "Le squadre che crei appariranno qui" in testi


def test_empty_state_senza_sottotitolo_non_crea_la_seconda_label(app):
    stato = EmptyState("Nessun risultato")
    testi = _label_texts(stato)
    # icona (pixmap, testo vuoto) + solo il titolo -> nessuna label di testo extra
    testi_non_vuoti = [t for t in testi if t]
    assert testi_non_vuoti == ["Nessun risultato"]


def _label_texts(widget) -> list[str]:
    from PySide6.QtWidgets import QLabel

    return [child.text() for child in widget.findChildren(QLabel)]
