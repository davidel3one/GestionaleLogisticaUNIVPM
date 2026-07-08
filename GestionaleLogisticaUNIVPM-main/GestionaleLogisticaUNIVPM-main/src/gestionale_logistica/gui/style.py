"""Foglio di stile (QSS) per l'aspetto a dashboard con menu laterale."""

DASHBOARD_QSS = """
QMainWindow, QWidget#ContenutoPrincipale {
    background-color: #f1f5f9;
}

QWidget#Sidebar {
    background-color: #1e293b;
}

QLabel#Logo {
    color: #ffffff;
    font-size: 16px;
    font-weight: 600;
    padding: 22px 20px 14px 20px;
}

QListWidget#MenuLaterale {
    background-color: #1e293b;
    border: none;
    outline: 0;
    font-size: 13px;
    padding-top: 4px;
}
QListWidget#MenuLaterale::item {
    color: #cbd5e1;
    padding: 12px 20px;
    border-left: 3px solid transparent;
}
QListWidget#MenuLaterale::item:selected {
    background-color: #334155;
    color: #ffffff;
    border-left: 3px solid #6366f1;
}
QListWidget#MenuLaterale::item:hover:!selected {
    background-color: #263349;
}

QLabel#TitoloSezione {
    font-size: 21px;
    font-weight: 600;
    color: #0f172a;
    padding-bottom: 8px;
}

QFrame#Scheda {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

QTableWidget {
    background-color: #ffffff;
    border: none;
    gridline-color: #eef1f5;
    selection-background-color: #e0e7ff;
    selection-color: #1e1b4b;
}
QTableWidget::item {
    padding: 4px 6px;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 600;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}

QGroupBox {
    font-weight: 600;
    color: #334155;
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 8px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #0f172a;
}

QLineEdit, QDateTimeEdit, QComboBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 8px;
    background-color: #ffffff;
    selection-background-color: #6366f1;
}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus {
    border: 1px solid #6366f1;
}

QPushButton {
    background-color: #6366f1;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #4f46e5;
}
QPushButton:pressed {
    background-color: #4338ca;
}
QPushButton#PulsanteElimina {
    background-color: #ef4444;
}
QPushButton#PulsanteElimina:hover {
    background-color: #dc2626;
}
"""
