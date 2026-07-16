"""Stile scrollbar minimale condiviso: sottile, trasparente, senza le frecce sopra/sotto.

Non nel mockup Sketch (nessuna scrollbar disegnata in un mockup statico) — richiesta esplicita
dell'utente di uno stile minimale coerente con la palette dell'app, non delle scrollbar di
sistema. Riusa `LABEL_COLOR` (`#8A93A0`, gia' usato per label/placeholder in `form_field.py`) in
trasparenza invece di introdurre un colore nuovo.
"""

from __future__ import annotations

_HANDLE_COLOR = "rgba(138, 147, 160, 0.35)"
_HANDLE_COLOR_HOVER = "rgba(138, 147, 160, 0.6)"

MINIMAL_SCROLLBAR_QSS = f"""
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {_HANDLE_COLOR};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {_HANDLE_COLOR_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {_HANDLE_COLOR};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {_HANDLE_COLOR_HOVER};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
"""
