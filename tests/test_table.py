"""Regressione per lo scorrimento verticale interno di Table (stesso pattern headless di
test_form_field.py)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gestionale_logistica.gui.components import ColumnDef, Table


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _righe(n: int) -> list[dict]:
    return [{"nome": f"Riga {i}"} for i in range(n)]


def test_table_rows_dentro_una_scrollarea(app):
    tabella = Table([ColumnDef(key="nome", label="Nome")])
    tabella.set_rows(_righe(5))

    assert tabella._rows_scroll.widget() is tabella._rows_container


def test_table_senza_vincoli_di_altezza_mostra_tutte_le_righe_senza_scroll(app):
    # Il sizeHint della QScrollArea interna deve riflettere l'altezza reale del contenuto
    # (fix di _RowsScrollArea.sizeHint) - altrimenti, senza un genitore che la stringa
    # (es. dentro un Modal senza stretch), la Table si sarebbe "accorciata" da sola tagliando
    # l'ultima riga sotto il footer.
    tabella = Table([ColumnDef(key="nome", label="Nome")], show_footer=False)
    tabella.set_rows(_righe(5))
    tabella.resize(tabella.sizeHint())
    tabella.show()
    app.processEvents()

    bar = tabella._rows_scroll.verticalScrollBar()
    assert bar.maximum() == 0


def test_table_con_altezza_ridotta_scorre_internamente(app):
    # Quando invece un genitore le da' meno spazio del sizeHint (stretch di pagina, o un
    # setMaximumHeight esplicito) la QScrollArea interna deve scorrere per davvero.
    tabella = Table([ColumnDef(key="nome", label="Nome")], show_footer=False)
    tabella.set_rows(_righe(20))
    tabella.show()
    tabella.resize(tabella.sizeHint().width(), 200)
    app.processEvents()

    bar = tabella._rows_scroll.verticalScrollBar()
    assert bar.maximum() > 0
