"""Regressione GUI per il componente Sidebar (navigazione, active, collasso, logout).

Nessun pytest-qt nel progetto: si usa una singola QApplication a livello di modulo con
piattaforma "offscreen", stesso pattern di test_modal.py/test_tooltip.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.components.sidebar import (
    WIDTH_COLLAPSED,
    WIDTH_EXPANDED,
    Sidebar,
    SidebarItem,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _items() -> list[SidebarItem]:
    return [
        SidebarItem("dashboard", "Dashboard", "layout-dashboard"),
        SidebarItem("ordini", "Ordini", "package"),
        SidebarItem("viaggi", "Viaggi", "route"),
    ]


def test_sidebar_richiede_almeno_una_voce(app):
    with pytest.raises(ValueError):
        Sidebar([])


def test_prima_voce_attiva_di_default(app):
    sidebar = Sidebar(_items())
    assert sidebar.current_item == "dashboard"


def test_larghezza_iniziale_espansa(app):
    sidebar = Sidebar(_items())
    assert sidebar.width() == WIDTH_EXPANDED
    assert sidebar.collapsed is False


def test_set_active_aggiorna_current_item(app):
    sidebar = Sidebar(_items())
    sidebar.set_active("ordini")
    assert sidebar.current_item == "ordini"


def test_set_active_id_inesistente_non_cambia_current(app):
    sidebar = Sidebar(_items())
    sidebar.set_active("inesistente")
    assert sidebar.current_item == "dashboard"


def test_set_active_non_emette_navigated(app):
    sidebar = Sidebar(_items())
    emessi: list[str] = []
    sidebar.navigated.connect(emessi.append)
    sidebar.set_active("viaggi")
    assert emessi == []


def test_click_voce_emette_navigated_e_attiva(app):
    sidebar = Sidebar(_items())
    emessi: list[str] = []
    sidebar.navigated.connect(emessi.append)
    sidebar._on_nav_clicked("viaggi")
    assert emessi == ["viaggi"]
    assert sidebar.current_item == "viaggi"


def test_toggle_collapsed_cambia_larghezza_e_stato(app):
    sidebar = Sidebar(_items())
    sidebar.toggle_collapsed()
    assert sidebar.collapsed is True
    assert sidebar.width() == WIDTH_COLLAPSED
    sidebar.toggle_collapsed()
    assert sidebar.collapsed is False
    assert sidebar.width() == WIDTH_EXPANDED


def test_collapsed_changed_emesso_solo_al_cambio(app):
    sidebar = Sidebar(_items())
    stati: list[bool] = []
    sidebar.collapsedChanged.connect(stati.append)
    sidebar.set_collapsed(True)
    sidebar.set_collapsed(True)  # nessun cambio -> nessun segnale
    sidebar.set_collapsed(False)
    assert stati == [True, False]


def test_logout_inoltrato(app):
    sidebar = Sidebar(_items())
    chiamato: list[bool] = []
    sidebar.logoutRequested.connect(lambda: chiamato.append(True))
    sidebar._user_row.logoutRequested.emit()
    assert chiamato == [True]


def test_tooltip_solo_in_stato_collassato(app):
    sidebar = Sidebar(_items())
    nav = sidebar._nav_items[0]
    assert nav.toolTip() == ""
    sidebar.set_collapsed(True)
    assert nav.toolTip() == "Dashboard"
    sidebar.set_collapsed(False)
    assert nav.toolTip() == ""
