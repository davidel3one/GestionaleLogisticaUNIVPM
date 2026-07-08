import enum
import re
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gestionale_logistica.database import crud
from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import (
    CategoriaConsegna,
    StatoEsito,
    StatoOrdine,
    StatoViaggio,
)
from gestionale_logistica.gui.style import DASHBOARD_QSS

_CODICE_FISCALE_FORMATO_RE = re.compile(
    r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$"
)

# Tabelle ufficiali di conversione per il calcolo del carattere di controllo (16° carattere)
# del codice fiscale italiano: valore per posizione dispari/pari (1-indicizzate).
_CF_VALORI_DISPARI = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17, "I": 19, "J": 21,
    "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6, "R": 8, "S": 12, "T": 14,
    "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
}
_CF_VALORI_PARI = {c: i for i, c in enumerate("0123456789")}
_CF_VALORI_PARI.update({c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})


def _codice_fiscale_valido(cf: str) -> bool:
    """Verifica formato (16 caratteri nella struttura corretta) e carattere di controllo."""
    cf = cf.upper()
    if not _CODICE_FISCALE_FORMATO_RE.match(cf):
        return False
    somma = sum(
        _CF_VALORI_DISPARI[ch] if i % 2 == 0 else _CF_VALORI_PARI[ch]
        for i, ch in enumerate(cf[:15])
    )
    return chr(ord("A") + somma % 26) == cf[15]


@dataclass
class Campo:
    """Descrive un campo del form di inserimento: nome colonna del modello e tipo di widget."""

    nome: str
    tipo: str = "testo"  # testo | numero | bool | data | enum
    enum_cls: type | None = None
    obbligatorio: bool = True  # se False, un testo vuoto viene salvato come None


def _valida_dipendente(dati: dict) -> Optional[str]:
    if not _codice_fiscale_valido(dati["codice_fiscale"]):
        return "Il codice fiscale non e' valido (formato o carattere di controllo errato)."
    dati["codice_fiscale"] = dati["codice_fiscale"].upper()
    return None


def _valida_viaggio(dati: dict) -> Optional[str]:
    if dati["data_arrivo_prevista"] <= dati["data_partenza_prevista"]:
        return "La data di arrivo prevista deve essere successiva alla data di partenza prevista."
    return None


def _valida_esito(dati: dict) -> Optional[str]:
    # Glossario: la Causale e' obbligatoria quando l'Esito e' "Fallito".
    if dati["stato_esito"] == StatoEsito.FALLITO and not dati.get("causale_id"):
        return "Un Esito 'Fallito' richiede obbligatoriamente una Causale (codice CausaleFallimento)."
    return None


# Sezioni principali: nome tab, CRUD, colonne mostrate in tabella, campi del form di inserimento,
# validazione aggiuntiva (regole di business che vanno oltre il singolo campo).
# Le chiavi esterne (es. viaggio_id, composizione_id) vanno digitate a mano finche' non ci sono
# selettori collegati; la loro esistenza e' comunque garantita dal vincolo FK a livello di database.
SEZIONI = [
    (
        "Dipendenti",
        crud.dipendente,
        ["id", "nome", "cognome", "codice_fiscale", "attivo"],
        [
            Campo("id"),
            Campo("nome"),
            Campo("cognome"),
            Campo("codice_fiscale"),
            Campo("data_assunzione", "data"),
            Campo("attivo", "bool"),
            Campo("certificazione_gas", "bool"),
        ],
        _valida_dipendente,
    ),
    (
        "Camion",
        crud.camion,
        ["id", "targa", "tipo_mezzo", "sponda_idraulica", "attivo"],
        [
            Campo("id"),
            Campo("targa"),
            Campo("tipo_mezzo"),
            Campo("sponda_idraulica", "bool"),
            Campo("data_acquisizione", "data"),
            Campo("attivo", "bool"),
        ],
        None,
    ),
    (
        "Squadre",
        crud.squadra,
        ["id", "attiva", "data_creazione"],
        [
            Campo("id"),
            Campo("attiva", "bool"),
            Campo("data_creazione", "data"),
        ],
        None,
    ),
    (
        "Viaggi",
        crud.viaggio,
        ["id", "data_partenza_prevista", "stato_viaggio"],
        [
            Campo("id"),
            Campo("data_partenza_prevista", "data"),
            Campo("data_arrivo_prevista", "data"),
            Campo("stato_viaggio", "enum", StatoViaggio),
            Campo("foglio_viaggio_id"),
            Campo("composizione_id"),
        ],
        _valida_viaggio,
    ),
    (
        "Ordini",
        crud.ordine,
        ["id", "destinazione", "categoria_consegna", "stato_ordine"],
        [
            Campo("id"),
            Campo("destinazione"),
            Campo("cliente"),
            Campo("peso", "numero"),
            Campo("volume_cargo", "numero"),
            Campo("categoria_consegna", "enum", CategoriaConsegna),
            Campo("stato_ordine", "enum", StatoOrdine),
        ],
        None,
    ),
    (
        "Esiti",
        crud.esito_consegna,
        ["id", "stato_esito", "data_registrazione", "causale_id"],
        [
            Campo("stato_esito", "enum", StatoEsito),
            Campo("data_registrazione", "data"),
            Campo("ordine_id"),
            Campo("registro_id"),
            Campo("causale_id", obbligatorio=False),
        ],
        _valida_esito,
    ),
]


class SezioneWidget(QWidget):
    """Tabella con i record esistenti + form minimo per aggiungere/eliminare, per una sezione."""

    def __init__(
        self,
        crud_obj,
        colonne: list[str],
        campi: list[Campo],
        valida_extra: Callable[[dict], Optional[str]] | None = None,
    ):
        super().__init__()
        self.crud_obj = crud_obj
        self.colonne = colonne
        self.campi = campi
        self.valida_extra = valida_extra
        self.editor_per_campo: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        scheda_tabella = QFrame()
        scheda_tabella.setObjectName("Scheda")
        tabella_layout = QVBoxLayout(scheda_tabella)
        tabella_layout.setContentsMargins(1, 1, 1, 1)
        tabella_layout.setSpacing(0)

        self.campo_ricerca = QLineEdit()
        self.campo_ricerca.setObjectName("CampoRicerca")
        self.campo_ricerca.setPlaceholderText("Cerca...")
        self.campo_ricerca.textChanged.connect(self._filtra)
        barra_ricerca = QWidget()
        barra_ricerca_layout = QHBoxLayout(barra_ricerca)
        barra_ricerca_layout.setContentsMargins(12, 10, 12, 10)
        barra_ricerca_layout.addWidget(self.campo_ricerca)
        tabella_layout.addWidget(barra_ricerca)

        self.tabella = QTableWidget()
        self.tabella.setColumnCount(len(colonne))
        self.tabella.setHorizontalHeaderLabels(colonne)
        self.tabella.setAlternatingRowColors(True)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabella.horizontalHeader().setStretchLastSection(True)
        tabella_layout.addWidget(self.tabella)
        layout.addWidget(scheda_tabella, 1)

        gruppo_form = QGroupBox("Nuovo record")
        form_layout = QFormLayout(gruppo_form)
        for campo in campi:
            editor = self._crea_editor(campo)
            self.editor_per_campo[campo.nome] = editor
            etichetta = campo.nome + ("" if campo.obbligatorio else " (opzionale)")
            form_layout.addRow(etichetta, editor)
        layout.addWidget(gruppo_form)

        pulsanti = QHBoxLayout()
        btn_aggiungi = QPushButton("Aggiungi")
        btn_aggiungi.clicked.connect(self._aggiungi)
        btn_elimina = QPushButton("Elimina selezionato")
        btn_elimina.setObjectName("PulsanteElimina")
        btn_elimina.clicked.connect(self._elimina_selezionato)
        pulsanti.addStretch()
        pulsanti.addWidget(btn_aggiungi)
        pulsanti.addWidget(btn_elimina)
        layout.addLayout(pulsanti)

        self.aggiorna_tabella()

    def _crea_editor(self, campo: Campo) -> QWidget:
        if campo.tipo == "bool":
            return QCheckBox()
        if campo.tipo == "data":
            editor = QDateTimeEdit(QDateTime.currentDateTime())
            editor.setCalendarPopup(True)
            return editor
        if campo.tipo == "enum":
            editor = QComboBox()
            for valore in campo.enum_cls:
                editor.addItem(valore.value, valore)
            return editor
        return QLineEdit()

    def aggiorna_tabella(self) -> None:
        with SessionLocal() as db:
            righe = self.crud_obj.get_all(db)

        self.tabella.setRowCount(len(righe))
        for r, riga in enumerate(righe):
            for c, colonna in enumerate(self.colonne):
                valore = getattr(riga, colonna, "")
                if isinstance(valore, enum.Enum):
                    testo = valore.value
                elif valore is None:
                    testo = ""
                else:
                    testo = str(valore)
                self.tabella.setItem(r, c, QTableWidgetItem(testo))

        self._filtra(self.campo_ricerca.text())

    def _filtra(self, testo: str) -> None:
        """Nasconde le righe che non contengono il testo cercato in nessuna colonna visibile."""
        testo = testo.strip().lower()
        for r in range(self.tabella.rowCount()):
            if not testo:
                self.tabella.setRowHidden(r, False)
                continue
            corrisponde = any(
                testo in item.text().lower()
                for c in range(self.tabella.columnCount())
                if (item := self.tabella.item(r, c)) is not None
            )
            self.tabella.setRowHidden(r, not corrisponde)

    def _leggi_form(self) -> Optional[dict]:
        """Legge e valida ogni campo del form. Restituisce None (mostrando l'errore) se non valido."""
        dati: dict = {}
        for campo in self.campi:
            editor = self.editor_per_campo[campo.nome]

            if campo.tipo == "bool":
                dati[campo.nome] = editor.isChecked()

            elif campo.tipo == "data":
                dati[campo.nome] = editor.dateTime().toPython()

            elif campo.tipo == "enum":
                dati[campo.nome] = editor.currentData()

            elif campo.tipo == "numero":
                testo = editor.text().strip()
                try:
                    valore = float(testo)
                except ValueError:
                    QMessageBox.warning(self, "Dato non valido", f"'{campo.nome}' deve essere un numero.")
                    return None
                if valore <= 0:
                    QMessageBox.warning(self, "Dato non valido", f"'{campo.nome}' deve essere maggiore di zero.")
                    return None
                dati[campo.nome] = valore

            else:  # testo
                testo = editor.text().strip()
                if not testo:
                    if campo.obbligatorio:
                        QMessageBox.warning(self, "Dato mancante", f"Il campo '{campo.nome}' e' obbligatorio.")
                        return None
                    testo = None
                dati[campo.nome] = testo

        if self.valida_extra:
            errore = self.valida_extra(dati)
            if errore:
                QMessageBox.warning(self, "Dato non valido", errore)
                return None

        return dati

    def _aggiungi(self) -> None:
        dati = self._leggi_form()
        if dati is None:
            return
        try:
            with SessionLocal() as db:
                self.crud_obj.create(db=db, obj_in=dati)
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile aggiungere il record: {e}")
            return
        self.aggiorna_tabella()

    def _elimina_selezionato(self) -> None:
        riga_selezionata = self.tabella.currentRow()
        if riga_selezionata < 0:
            return
        colonna_id = self.colonne.index("id") if "id" in self.colonne else 0
        item = self.tabella.item(riga_selezionata, colonna_id)
        if item is None:
            return
        try:
            with SessionLocal() as db:
                self.crud_obj.delete(db=db, id=item.text())
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile eliminare il record: {e}")
            return
        self.aggiorna_tabella()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestionale Logistica")
        self.resize(1150, 680)
        self.setStyleSheet(DASHBOARD_QSS)

        centrale = QWidget()
        self.setCentralWidget(centrale)
        layout_principale = QHBoxLayout(centrale)
        layout_principale.setContentsMargins(0, 0, 0, 0)
        layout_principale.setSpacing(0)

        layout_principale.addWidget(self._crea_sidebar())

        contenuto = QWidget()
        contenuto.setObjectName("ContenutoPrincipale")
        layout_contenuto = QVBoxLayout(contenuto)
        layout_contenuto.setContentsMargins(28, 24, 28, 24)

        self.titolo_sezione = QLabel()
        self.titolo_sezione.setObjectName("TitoloSezione")
        layout_contenuto.addWidget(self.titolo_sezione)

        self.stack = QStackedWidget()
        layout_contenuto.addWidget(self.stack)
        for nome, crud_obj, colonne, campi, valida_extra in SEZIONI:
            self.stack.addWidget(SezioneWidget(crud_obj, colonne, campi, valida_extra))

        layout_principale.addWidget(contenuto, 1)

        self.menu.currentRowChanged.connect(self._cambia_sezione)
        self.menu.setCurrentRow(0)

    def _crea_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel("Gestionale\nLogistica")
        logo.setObjectName("Logo")
        layout.addWidget(logo)

        self.menu = QListWidget()
        self.menu.setObjectName("MenuLaterale")
        self.menu.setFrameShape(QFrame.NoFrame)
        for nome, *_ in SEZIONI:
            self.menu.addItem(nome)
        layout.addWidget(self.menu, 1)

        return sidebar

    def _cambia_sezione(self, indice: int) -> None:
        if indice < 0:
            return
        self.stack.setCurrentIndex(indice)
        self.titolo_sezione.setText(SEZIONI[indice][0])
