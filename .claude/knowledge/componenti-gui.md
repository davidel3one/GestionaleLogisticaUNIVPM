# Componenti GUI riusabili

Libreria di componenti PySide6 in `src/gestionale_logistica/gui/components/`, pensata per non riscrivere lo stesso widget/QSS in ogni pagina. Fonte di verità per ogni dettaglio visivo (colori, spaziature, radius, font, icone): il file `sketch/gui-design.sketch` — ogni componente qui è stato costruito ispezionando le istanze reali nel mockup, non a memoria/a occhio.

Import: `from gestionale_logistica.gui.components import AuthLogo, BooleanToggle, Button, ButtonVariant, Card, DatePicker, EmptyState, IconChip, IconChipVariant, LinkButton, Modal, MultiSelect, OtpInput, PageHeader, SearchField, Select, Sidebar, SidebarItem, TextField, Tooltip, load_lucide_icon`.

**Nota sui componenti pagina-specifici**: questa libreria contiene solo componenti genuinamente **riusabili tra pagine diverse**. Componenti la cui forma è ritagliata esattamente su una pagina (es. `KpiCard`/`PlanningDayCard`/`ActivityRow` della Dashboard) vivono invece in `gui/<pagina>/components/`, non qui — vedi `## Componenti pagina-specifici` in fondo a questo file.

## Button

`Button(variant, text="", icon=None, parent=None)` — sottoclasse di `QPushButton`, 5 varianti visive fisse (nomi ripresi 1:1 dal mockup Sketch):

| `ButtonVariant` | Uso tipico | Icona |
|---|---|---|
| `PRIMARY` | Azione principale standard (blu pieno) | opzionale, 12×12 |
| `PRIMARY_LARGE` | CTA grande full-width (Login/OTP/Registrazione) | nessuna |
| `SECONDARY` | Azione secondaria/outline (Annulla, Importa CSV) | opzionale, 12×12 |
| `SECONDARY_HEADER_ADD` | Bottone "+" negli header pagina (Aggiungi dipendente, ecc.) | **obbligatoria**, 15×15 |
| `ICON_ONLY` | Chiusura modale (X) | **obbligatoria**, 15×15 |

```python
Button(ButtonVariant.PRIMARY, "Nuova pianificazione", load_lucide_icon("calendar-plus", "#FFFFFF", 12))
Button(ButtonVariant.PRIMARY_LARGE, "Accedi")
Button(ButtonVariant.SECONDARY, "Annulla")
Button(ButtonVariant.SECONDARY_HEADER_ADD, "Aggiungi dipendente", load_lucide_icon("circle-plus", "#2E2E2E", 15))
Button(ButtonVariant.ICON_ONLY, icon=load_lucide_icon("x", "#5B6472", 15))
```

`ICON_ONLY` e `SECONDARY_HEADER_ADD` sollevano `ValueError` se non ricevono un'icona — sono bottoni pensati per averla sempre.

**Personalizzazione**: il componente **non** espone parametri per colori/radius/padding — quei valori sono fissi per variante perché replicano esattamente il mockup. Se serve un aspetto diverso da uno dei 5, non forzare i parametri esistenti: è una nuova variante da aggiungere ispezionando prima Sketch (vedi "Aggiungere un componente nuovo" più sotto).

**Stati interattivi**: hover/pressed sono derivati automaticamente scurendo il colore base della variante (`HOVER_DARKEN`/`PRESSED_DARKEN` in `button.py`) — il mockup Sketch non li definisce esplicitamente. `disabled` si ottiene con `button.setEnabled(False)`: applica un'opacità ridotta (`DISABLED_OPACITY`, ~45%) a tutto il widget via `QGraphicsOpacityEffect` e cambia il cursore. Nessuno di questi valori viene dal mockup — se in futuro il team definisce colori espliciti per questi stati in Sketch, vanno sostituiti qui.

## Card

`Card(padding_horizontal=24, padding_vertical=20, spacing=16, parent=None)` — sottoclasse di `QFrame`, container generico: sfondo bianco, bordo 1px `#E5EAF0`, radius 14px, nessuna ombra. Layout verticale (`QVBoxLayout`) incluso di default.

```python
card = Card(padding_horizontal=20, padding_vertical=18, spacing=12)
card.add_widget(QLabel("3"))
card.add_widget(QLabel("ORDINI FALLITI"))
# oppure, per layout più complessi (es. una riga orizzontale dentro la card):
card.content_layout.addWidget(una_riga_orizzontale)
```

- `card.add_widget(widget)` — scorciatoia per il caso comune (aggiunge in coda al layout verticale).
- `card.content_layout` — il `QVBoxLayout` vero e proprio, esposto per accesso diretto quando serve altro (margini custom, `addLayout`, `insertWidget`, alignment, ecc.).

**Personalizzazione**: padding e spacing sono parametri liberi (non fissi come nel Button) perché il mockup li usa diversi in contesti diversi — default = valori del caso più generico (Filter Card). Passa valori diversi quando il contenuto lo richiede (es. le KPI Card nel mockup usano `padding_horizontal=20, padding_vertical=18, spacing=12`).

**Nota — divergenza intenzionale dal mockup**: nel file Sketch solo le "KPI Card" hanno il bordo 1px, le "Filter Card"/"Config Card"/"Avvio Card" non ce l'hanno. Su decisione esplicita dell'utente (2026-07-13) il componente è stato unificato: **il bordo è sempre presente**, per coerenza visiva in tutta l'app. Il file Sketch non è stato modificato di conseguenza — se lo si riapre e si nota la differenza, non è un errore di lettura, è uno scarto voluto.

`Card` non ha varianti KPI/Filter/Modal integrate — quelle sono composizioni di contenuto sopra `Card` (widget diversi dentro), non parametri del componente. Se in futuro serve un vero componente "KPI Card" (valore + trend + icona + etichetta, con il proprio layout interno fisso), va costruito come componente a parte che usa `Card` internamente, non aggiunto qui dentro.

## TabBar

`TabBar(labels: list[str], parent=None)` — selettore di tab orizzontale con indicatore ad underline animato. Componente puramente visivo: **non** gestisce il contenuto delle pagine (niente `QStackedWidget` integrato) — chi lo usa si iscrive al segnale per cambiare il contenuto altrove.

```python
tabs = TabBar(["Ordini", "Esiti"])
tabs.currentChanged.connect(lambda i: stacked_widget.setCurrentIndex(i))
```

- `labels`: qualunque numero di etichette (verificato nel mockup sia con 2 che con 3 tab, stesso stile).
- `tabs.current_index` — property di sola lettura con l'indice della tab attiva.
- `tabs.set_current_index(i)` — imposta la tab attiva programmaticamente (solleva `ValueError` se fuori range); non ri-emette il segnale se `i` è già quello corrente.
- `tabs.currentChanged` — `Signal(int)`, emesso quando l'utente clicca una tab diversa (o quando cambia via `set_current_index`).

**Personalizzazione**: nessun parametro di stile esposto (colori/font/gap sono fissi, replicano il mockup) — se serve un aspetto visivo diverso, non forzare i valori interni: è una variante nuova da valutare con l'utente.

**Stato hover** (non nel mockup): colore testo intermedio tra attivo e inattivo (`#22344D`, media tra `#163A6B` e `#2E2E2E` — nessun colore estraneo alla palette) + cursore a mano, stesso principio già usato in `Button`.

**Animazione underline**: lo spostamento/ridimensionamento dell'underline tra una tab e l'altra è animato (200ms, `QEasingCurve.OutCubic`) via due Qt `Property` (`underlineX`/`underlineWidth`) pilotate da `QPropertyAnimation` — richiesta esplicita dell'utente, il mockup statico non lo specifica (è un dettaglio di comportamento, non di stile visivo). Il cambio colore del testo resta istantaneo, non animato. Al primissimo render l'underline è già posizionata correttamente, senza scorrere da zero.

## Table

`Table(columns: list[ColumnDef], parent=None)` — tabella dati con colonne configurabili, header ordinabili e paginazione. Componente **presentazionale**: non ordina né pagina i dati da sola, emette segnali e chi la usa esegue una nuova query e ripassa righe/paginazione aggiornate. Scelta deliberata (2026-07-13): il team farà filtri/ordinamento server-side, quindi la Table non deve duplicare quella logica.

```python
def modifica(row: dict) -> None: ...
def elimina(row: dict) -> None: ...

tabella = Table([
    ColumnDef(key="id", label="ID", column_type=ColumnType.LINK, width=90),
    ColumnDef(key="cliente", label="Cliente", sortable=True, stretch=2),
    ColumnDef(key="indirizzo", label="Indirizzo", emphasis=TextEmphasis.SECONDARY, stretch=3),
    ColumnDef(key="stato", label="Stato", column_type=ColumnType.STATUS_BADGE, width=140),
    ColumnDef(key="azioni", label="Azioni", column_type=ColumnType.ACTIONS, width=76,
              actions=[RowAction("pencil", modifica), RowAction("trash-2", elimina)]),
])
tabella.set_rows([{"id": "#1040", "cliente": "Mario Rossi", "indirizzo": "...", "stato": "Consegnato"}, ...])
tabella.set_pagination(current_page=2, total_items=128, page_size=10)

tabella.sortRequested.connect(lambda colonna, ascending: ...)  # riquery server-side, poi set_rows
tabella.pageChanged.connect(lambda pagina: ...)                # riquery server-side, poi set_rows + set_pagination
```

- `set_rows(rows: list[dict])` — ogni riga è un dizionario chiave→valore (le chiavi corrispondono a `ColumnDef.key`). La Table non conosce entità ORM/di dominio, solo dizionari semplici.
- `set_pagination(current_page, total_items, page_size)` — calcola da sé il testo "X-Y / Z righe" e i numeri pagina da mostrare nel pager.
- `sortRequested = Signal(str, bool)` — chiave colonna + `ascending`, emesso al click su un header `sortable=True` (toggle automatico se si riclicca la stessa colonna).
- `pageChanged = Signal(int)` — pagina richiesta (1-based), emesso da click su numero pagina o freccia prev/next.

### Tipologie di colonna (`ColumnType`)

| Tipo | Uso | Note |
|---|---|---|
| `TEXT` (default) | testo semplice | `emphasis=TextEmphasis.PRIMARY` (`#2E2E2E`, default) o `.SECONDARY` (`#5B6472`, attenuato) |
| `LINK` | identificativi (`#1040`, `V-20260707-01`) | sempre blu `#2563C9`, SemiBold — solo visivo, nessun'interazione integrata |
| `STATUS_BADGE` | stato con pillola colorata | mappatura valore→(bg,testo) tramite `ColumnDef.status_colors` (dict), unita a una palette di default già pronta per 7 valori comuni (`Consegnato`/`Attivo`→verde, `Fallito`→rosso, `In consegna`→ambra, `Da pianificare`→grigio, `Pianificato`/`Proposto`→blu) — valori non mappati cadono sul grigio neutro |
| `BOOLEAN_BADGE` | flag sì/no (es. certificazione gas, sponda idraulica) | vero→pillola grigia con `true_label` (default "Sì"); falso→testo semplice con `false_label` (default "No", usa "—" se serve) |
| `ACTIONS` | icone azione per riga | `ColumnDef.actions: list[RowAction]`, ciascuna con `icon_name` (nome icona Lucide, vedi sezione icone), `callback(row: dict)`, `color` opzionale, `tooltip` opzionale — non limitato a modifica/elimina |

**Personalizzazione**: `ColumnDef.width` (larghezza fissa in px) oppure `ColumnDef.stretch` (fattore di stretch, colonne più larghe in proporzione) — non impostare entrambi sulla stessa colonna, `width` vince se presente. `status_colors` sulla singola colonna sovrascrive/estende la palette di default senza doverla ridefinire tutta.

**Fuori scope in questa versione**: colonna "progress bar" (percentuale + barra, vista nel mockup solo su Pianificazione — Assistita) — rimandata a quando quella pagina verrà costruita davvero, non ancora implementata.

**Nota — chrome esterna non condivisa con `Card`**: il contenitore della Table (bianco, radius 14px) **non ha bordo**, a differenza di `Card` che ora ha sempre il bordo (vedi sopra). Non è un'incoerenza: sono due componenti distinti con chrome verificate separatamente nel mockup, non `Table` che riusa `Card`.

## Modal

`Modal(title, subtitle=None, width=560, footer_buttons=None, parent=None)` — overlay modale **in-finestra** (non un `QDialog`): un `QWidget` a tutta area che si sovrappone al parent con backdrop semitrasparente, e la card bianca centrata al suo interno. Fornisce solo la chrome generica (header/backdrop/card/footer) — il contenuto è responsabilità del chiamante, esattamente come `Card` non integra i form specifici.

```python
footer_buttons = [Button(ButtonVariant.SECONDARY, "Annulla"), Button(ButtonVariant.PRIMARY, "Salva")]
modal = Modal("Aggiungi camion", subtitle="Compila i campi per registrare un nuovo mezzo",
              width=560, footer_buttons=footer_buttons, parent=main_window)
modal.add_widget(un_form_widget)               # oppure modal.content_layout.addWidget(...)
footer_buttons[0].clicked.connect(modal.close)  # "Annulla" chiude il modale
modal.closed.connect(...)                       # notifica quando il modale si chiude
modal.show_over(main_window)                    # mostra l'overlay sopra main_window
```

- `title`/`subtitle`: subtitle opzionale (assente in molte istanze del mockup: es. "Squadre — Dettaglio" non ce l'ha, i wizard/form sì). Se assente, il titolo resta comunque a `y=28` (non ricentrato).
- `width`: solo due famiglie verificate nel mockup, entrambe supportate come parametro libero — `560` (form di aggiunta/modifica: Camion, Dipendenti, Squadre, Ordini) e `900` (contenuti ricchi: dettaglio Squadra con tabella, wizard Importa CSV). L'altezza non è mai fissata: la decide il contenuto (`sizeHint`).
- `footer_buttons`: lista di `Button` opzionale, renderizzati a destra con gap 8px tra loro. Se `None`/vuota, niente footer/divider inferiore (caso dei modali di solo dettaglio/lettura, es. "Squadre — Dettaglio"). Il componente non aggiunge comportamento ai bottoni passati (es. "Annulla" non chiude da solo il modale): collega tu i segnali `clicked`.
- `modal.content_layout` (`QVBoxLayout`) / `modal.add_widget(widget)` — stesso pattern di `Card.content_layout`/`Card.add_widget()`.
- `modal.show_over(parent_widget)` — riparenta il modale su `parent_widget`, lo ridimensiona a tutta area e lo mostra; resta sincronizzato con `resizeEvent` del parent (event filter installato su `parent_widget`, rimosso automaticamente alla chiusura).
- `modal.close()` — chiude (eredita `QWidget.close()`). `modal.closed` — `Signal()` emesso alla chiusura, qualunque sia la causa (X, click sul backdrop, ESC, chiamata programmatica a `close()`).

**Valori esatti dal mockup**: backdrop `#0000004D` (nero ~30% alpha) su tutta l'area del parent; card sfondo `#FFFFFF`, **radius 14px**, nessun bordo, ombra `QGraphicsDropShadowEffect(color=#00000026, offset=(0,12), blur=40)` (lo `spread=-8` del mockup non è rappresentabile in Qt, ignorato — non critico); header altezza fissa 92px, titolo Inter 19px/SemiBold `#2E2E2E` a `(32,28)`, sottotitolo Inter 13px/Medium `#8A93A0` (stesso `HEADER_TEXT_COLOR` di `table.py`) a `(32,60)`; divider header 1px `#EDEFF3` (`DIVIDER_COLOR`) a `y=92`; pulsante chiusura = `Button(ButtonVariant.ICON_ONLY, icon=load_lucide_icon("x", "#5B6472", 15))`, hit-box 32×32, `y=24`, margine destro **24px se `width=560`, 32px se `width=900`** (nel componente: soglia `width >= 900`, non i due valori letterali — vale per qualunque `width` intermedio ipotetico); footer (se presente) divider 1px `#EDEFF3`, gap 16px prima dei pulsanti, padding 24px sotto.

**Scarti/scelte non misurabili da Sketch (dichiarati esplicitamente)**:
- Padding inferiore del content: **0px imposto dal componente**, deliberato — il mockup non lo specifica ("nessun padding fisso sotto"). Se un modale senza footer ha bisogno di spazio in fondo, va aggiunto nel contenuto passato dal chiamante, non nel componente.
- Gap tra i due bottoni del footer: 8px, scelto nel range 8-10px indicato (non è una misura pixel-precisa dal mockup, non critico).
- Click sul backdrop e tasto ESC chiudono il modale: comportamento standard atteso, non presente in un mockup statico — deciso in fase di implementazione, non richiede conferma perché è comportamento (non stile visivo).
- Margine close-button: assunto a soglia (`>= 900` → 32px, altrimenti 24px) perché nel mockup sono verificate solo le due famiglie di larghezza; se in futuro si introduce una terza larghezza, va verificato nel mockup e non assunto per estrapolazione.

**Personalizzazione**: nessuna, oltre a `title`/`subtitle`/`width`/`footer_buttons` — tutto il resto (colori, radius, spaziature dell'header/footer) è fisso perché replica il mockup, sullo stesso principio di `Button`.

## TextField

`TextField(label: str, placeholder: str = "", parent=None)` — sottoclasse di `QWidget`: label sopra (obbligatoria) + `QLineEdit` sotto, chrome del mockup (stato chiuso, unico stato disegnato).

```python
TextField("Capacità (kg)", placeholder="es. 1200")
TextField("Targa", placeholder="es. AB123CD")
```

- `field.value()` / `field.set_value(testo)` — API uniforme con `Select`/`BooleanToggle` (non `text()`/`setText()` di Qt), pensata per essere letta/scritta in modo omogeneo da chi assembla un form dentro un `Modal`.
- `field.valueChanged` — `Signal(str)`, inoltra `QLineEdit.textChanged` a ogni digitazione.
- Placeholder tipo "es. \<esempio\>", come nel mockup (Camion — Aggiungi, Dipendenti — Aggiungi).

**Valori esatti dal mockup**: container sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px, altezza fissa 34px, padding orizzontale 12px; testo/placeholder Inter 13px/Medium `#5B6472`; label sopra Inter 11px/SemiBold `#8A93A0`, gap verticale 4px tra label e campo (verificato su più istanze nel mockup, sempre 4px esatti). Il padding verticale (9px top/bottom nel mockup) non è impostato esplicitamente: l'altezza fissa di 34px più la centratura verticale automatica di Qt lo riproduce senza hardcodare margini che duplicherebbero il conteggio — stesso principio già usato in `Button` (es. `PRIMARY_LARGE`, altezza fissa senza padding verticale esplicito).

**Assunzione segnalata**: il colore del placeholder è impostato uguale a quello del testo digitato (`#5B6472`) tramite `QPalette::PlaceholderText` — senza questo, Qt schiarirebbe automaticamente il placeholder. Il mockup non mostra uno stato "campo con testo digitato" separato da quello con placeholder, quindi non c'è modo di verificare che siano davvero identici; è l'assunzione più sicura (nessuna differenziazione esplicita nel mockup).

**Parametro `password: bool = False`** (aggiunto 2026-07-15 per i campi Password/Conferma password delle schermate di autenticazione): se `True`, imposta `QLineEdit.EchoMode.Password` (testo mascherato a pallini, come nel mockup Login/Registrazione). Nessun impatto sui campi esistenti (default `False`, stesso comportamento di prima).

## Select

`Select(label: str, options: list[str], placeholder: str = "", parent=None)` — sottoclasse di `QWidget`: label sopra + campo cliccabile (chevron a destra) che apre un `QMenu` con le opzioni.

```python
tipo = Select("Tipo mezzo", options=["Furgone", "Camion", "Bilico"], placeholder="Seleziona")
tipo.valueChanged.connect(...)
```

- `select.value()` — `str | None` (`None` finché nessuna opzione è stata scelta).
- `select.set_value(valore)` — imposta il valore programmaticamente (`None` per tornare al placeholder) e aggiorna il testo mostrato.
- `select.valueChanged` — `Signal(str)`, emesso alla scelta di una voce dal popup o a `set_value()` esplicito.

**Valori esatti dal mockup (stato chiuso)**: stessa chrome di `TextField` (container `#FFFFFF`/bordo `#E5EAF0`/radius 9px/altezza 34px/padding 12px, testo Inter 13px/Medium `#5B6472`, label Inter 11px/SemiBold `#8A93A0` con gap 4px) più chevron-down 14×14 allineato a destra, gap 8px dal testo (era uno Stack orizzontale nel mockup).

**Assunzioni segnalate esplicitamente (non verificate nel mockup, che mostra solo lo stato chiuso)**:
- **Colore dell'icona chevron**: `#5B6472`, riusato dal testo del campo — il mockup non specifica un colore diverso per l'icona, quindi si riusa quello del testo come assunzione più sicura invece di introdurre un colore non misurato.
- **Popup delle opzioni**: nessun frame del mockup disegna il Select aperto. Per coerenza con gli altri componenti già fatti, il popup (`QMenu`) è stilato con: sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px (stessi token del resto), voce selezionata/hover con sfondo `#F7F9FC` (lo stesso grigio riusato per lo sfondo dei bottoni `SECONDARY` in `button.py`, per non introdurre un token nuovo), testo voci Inter 13px/Medium `#5B6472`. Scelta di implementazione non verificata, analoga a come `Modal` documenta "click sul backdrop chiude" come comportamento standard non nel mockup statico.

**Nota storica**: nella prima iterazione Multiselect e Date Picker erano stati rimandati (nessun frame del mockup li mostra aperti). L'utente ha poi deciso esplicitamente come implementarli senza aggiornare il mockup — vedi `## DatePicker` e `## MultiSelect` più sotto: non sono assunzioni di questa libreria, sono scelte confermate dall'utente.

## BooleanToggle

`BooleanToggle(label: str, parent=None)` — sottoclasse di `QWidget`: label sopra + due pillole affiancate "Sì"/"No" (etichette fisse, **non** un segmented control generico a N opzioni — nel mockup è specificamente un toggle booleano).

```python
sponda = BooleanToggle("Sponda idraulica")
sponda.valueChanged.connect(...)
```

- `toggle.value()` — `bool` (default `False`, cioè "No" selezionato).
- `toggle.set_value(True | False)` — seleziona programmaticamente la pillola corrispondente.
- `toggle.valueChanged` — `Signal(bool)`, emesso al click su una pillola o a `set_value()` esplicito.

**Valori esatti dal mockup**: due pillole 56×34px, gap 8px, border-radius 17px (capsula, = altezza/2); stato selezionato: sfondo `#FFFFFF`, bordo 1px `#E5EAF0`; stato non selezionato: sfondo `#EAEAEA`, nessun bordo; testo in entrambi gli stati Inter 13px/Medium `#5B6472` (stesso colore, verificato — il mockup non differenzia il colore testo tra selezionato/non selezionato); label sopra Inter 11px/SemiBold `#8A93A0`, gap 4px.

## DatePicker

`DatePicker(label: str, parent=None)` — sottoclasse di `QWidget`: label sopra + `QDateEdit` nativo Qt con `calendarPopup=True`.

```python
data = DatePicker("Data consegna")
data.valueChanged.connect(...)
data.set_value(QDate(2026, 7, 11))
```

- `field.value()` — `QDate` (default: data odierna, `QDate.currentDate()`, comportamento nativo di `QDateEdit`).
- `field.set_value(QDate(...))` — imposta la data programmaticamente.
- `field.valueChanged` — `Signal(QDate)`, inoltra `QDateEdit.dateChanged`.
- Formato di visualizzazione: `dd/MM/yyyy` (costante `DATE_FORMAT` in `form_field.py`), coerente con gli esempi nel mockup ("11/07/2026", "14/10/2020").

**Decisione esplicita dell'utente (non un'assunzione)**: il calendario a comparsa è quello **nativo di Qt/OS**, non ridisegnato — nessuno stile del sistema di design applicato al popup del calendario in sé. Solo il chrome del campo chiuso è ristilizzato per combaciare con gli altri field: sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px, altezza 34px, testo Inter 13px/Medium `#5B6472` (stessi identici token/costanti di `TextField`/`Select`, nessun valore duplicato). Il pulsantino calendario integrato di `QDateEdit` (freccia a destra) non è stato toccato: rimuoverlo/sostituirlo avrebbe richiesto stilizzare `QDateEdit::drop-down`, fuori dal perimetro della richiesta ("solo il chrome del campo chiuso").

## MultiSelect

`MultiSelect(label: str, options: list[str], placeholder: str = "Seleziona...", parent=None)` — sottoclasse di `QWidget`: stessa chrome esterna chiusa di `Select` (riusa `_SelectBox`), popup con una `QCheckBox` per opzione invece di un `QAction` singola.

```python
giorni = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer", "Gio", "Ven"])
giorni.valueChanged.connect(...)
giorni.set_value(["Lun", "Mer"])
```

- `campo.value()` — `list[str]` (vuota finché nessuna opzione è selezionata).
- `campo.set_value(valori)` — imposta la selezione programmaticamente (filtra silenziosamente valori non presenti in `options`).
- `campo.valueChanged` — `Signal(list)`, emesso a ogni check/uncheck di una voce nel popup o a `set_value()` esplicito.
- Testo mostrato nel campo chiuso: `placeholder` (default `"Seleziona..."`) se vuoto, il nome dell'opzione se una sola selezionata, `"N selezionati"` se più di una — testo di sistema, non presente nel mockup.

**Decisione esplicita dell'utente (non un'assunzione)**: nessun frame del mockup mostra un multiselect aperto. Pattern "testo riassuntivo nel campo chiuso + popup con checkbox" scelto dall'utente in assenza di mockup, non dedotto. Il popup riusa `_build_popup_chrome` (helper condiviso, fattorizzato da `Select` invece di duplicare lo stesso QSS): sfondo `#FFFFFF`, bordo `#E5EAF0`, radius 9px, voce hover `#F7F9FC`, testo Inter 13px/Medium `#5B6472` — stessi token del popup Select. Le checkbox restano native Qt (`QCheckBox`), solo ricolorate/spaziate con lo stesso QSS delle voci del menu Select; il popup resta aperto tra un check e l'altro (comportamento standard di `QWidgetAction` con widget custom dentro un `QMenu`, necessario per selezionare più voci in sequenza).

## Tooltip

`Tooltip(text: str, parent=None)` — sottoclasse di `QLabel` in `gui/components/tooltip.py`: icona info 18×18, autosufficiente (icona + comportamento hover inclusi), da affiancare a una label/campo in un layout esistente. Verificato nel mockup su 3 istanze identiche ("Info Popover"), non un'istanza isolata.

```python
riga = QHBoxLayout()
riga.addWidget(_build_label("Capacità massima"))
riga.addWidget(Tooltip("Il peso massimo trasportabile, comprensivo di imballaggi (RNF4)."))
```

- Nessun widget "trigger" esterno da decorare: `Tooltip` **è** l'icona cliccabile/hover-abile, si aggiunge direttamente a un layout come qualunque altro widget — scelto perché è l'uso più naturale nei form di questo progetto (spiegazioni accanto a label/campi, es. vincoli RNF), coerente con l'autosufficienza degli altri componenti (`Button`, `Card`).
- `tooltip.show_popover()` / `tooltip.hide_popover()` — API pubblica per controllo programmatico, oltre al comportamento hover automatico; sono gli stessi metodi invocati internamente da `enterEvent`/`leaveEvent`.
- Il popover è una finestra top-level frameless (`Qt.WindowType.ToolTip`), non un widget figlio: non viene ritagliato dai bordi del parent e resta sopra tutto, comportamento standard per un tooltip flottante.

**Valori esatti dal mockup**: popover sfondo `#EAEAEA`, radius 10px, nessun bordo, ombra `QGraphicsDropShadowEffect(color=#00000026, offset=(0,8), blur=24)` (lo `spread=-4` del mockup non è rappresentabile in Qt, ignorato — stessa non-criticità già annotata per l'ombra di `Modal`); testo Inter 12px/Medium `#2E2E2E`, padding 12px verticale / 16px orizzontale; icona trigger 18×18 (Lucide `info`, identificata per confronto strutturale dei path SVG, non a occhio); gap orizzontale 10px tra icona e popover, popover verticalmente centrato rispetto all'icona; nessuna freccia/puntatore verso l'icona (il popover nel mockup ha un solo figlio, il testo).

**Assunzioni segnalate esplicitamente**:
- **Colore dell'icona**: `#8A93A0`, riuso del token già usato per le label dei campi (`LABEL_COLOR` in `form_field.py`) — il mockup non specifica un colore per l'icona info, solo forma e dimensione.
- **Larghezza massima del popover (320px)**: il box nel mockup è largo 560px ma il testo reale occupa solo 331px — è quasi certamente un artefatto di allineamento del canvas Sketch, non una larghezza intenzionale (segnalato esplicitamente dall'utente). Il componente usa larghezza auto (content-driven, si adatta al testo) con un cap di 320px scelto per far andare a capo spiegazioni molto lunghe invece di crescere all'infinito in orizzontale — valore non misurato, scelta di implementazione.
- **Comportamento hover** (mostra al passaggio del mouse, nasconde all'uscita): standard atteso, non verificabile in un mockup statico — stessa logica già usata per "click sul backdrop chiude" in `Modal`, non richiede conferma perché è comportamento, non stile visivo.

## Sidebar

`Sidebar(items: list[SidebarItem], app_name="LogiPlan", user_name="Davide", parent=None)` — sottoclasse di `QWidget`: barra di navigazione laterale a tutta altezza con logo in alto, voci di navigazione al centro e riga utente (con logout) in basso. Espandibile/collassabile a rail. Componente **puramente di navigazione**: non integra un `QStackedWidget` né gestisce il contenuto delle pagine — chi lo usa si iscrive a `navigated` per cambiare pagina altrove (stesso principio di `TabBar`). Per la finestra completa Sidebar + area contenuti vedi `## AppShell / Finestra base` sotto.

```python
from gestionale_logistica.gui.components import Sidebar, SidebarItem

items = [
    SidebarItem("dashboard", "Dashboard", "layout-dashboard"),
    SidebarItem("ordini", "Ordini", "package"),
    SidebarItem("viaggi", "Viaggi", "route"),
]
sidebar = Sidebar(items, app_name="LogiPlan", user_name="Davide")
sidebar.navigated.connect(lambda item_id: stacked_widget.setCurrentIndex(...))
sidebar.logoutRequested.connect(esegui_logout)
```

- `SidebarItem(id: str, label: str, icon_name: str)` — dataclass che descrive una voce: `id` stabile usato nei segnali/`set_active`, `label` mostrata, `icon_name` = nome icona Lucide (deve esistere in `gui/assets/icons/`, vedi sezione Icone).
- `sidebar.set_active(item_id)` — evidenzia la voce indicata; **solo aggiornamento visivo, non emette `navigated`** (id inesistente = no-op silenzioso). Serve a sincronizzare l'highlight quando la pagina cambia da fuori.
- `sidebar.toggle_collapsed()` / `sidebar.set_collapsed(bool)` — collassa/espande la barra; `set_collapsed` è idempotente (nessun segnale se lo stato non cambia).
- `sidebar.collapsed` — property di sola lettura, stato corrente.
- `sidebar.current_item` — property di sola lettura, `id` della voce attiva (`None` se nessuna).
- `sidebar.navigated` — `Signal(str)`, emesso al click su una voce (dopo aver aggiornato l'highlight interno) con l'`id` della voce.
- `sidebar.logoutRequested` — `Signal()`, emesso al click sul pulsante logout.
- `sidebar.collapsedChanged` — `Signal(bool)`, emesso a ogni cambio effettivo di stato collassato.
- Alla costruzione la **prima voce** è attiva di default. `items` vuota solleva `ValueError`.

**Valori esatti dal mockup (stato espanso)**: larghezza 240px, altezza piena, sfondo `#FCFDFE`. Logo Row: tassello 28×28 radius 8 sfondo `#2563C9` con dentro `load_lucide_icon("route", "#FFFFFF", 16)`, nome app Inter 17px/Medium `#163A6B`, toggle a destra icona `chevron-left` 18×18. Voci nav: riga h50, icona 18×18 con pad-left 20, label a x50 Inter 14; **attiva** = sfondo riga `#D6EAFB` + testo SemiBold `#163A6B` + icona `#163A6B`; **inattiva** = sfondo trasparente + testo Medium `#2E2E2E` + icona `#2E2E2E`. Divider 1px `#E3EFFB` sotto la Logo Row e sopra la User Row. User Row: avatar cerchio 32×32 `#2563C9` con iniziale bianca del `user_name`, nome Inter 14 `#2E2E2E`, pulsante `log-out` ~16px a destra.

**Stato collassato (rail 72px)**: decisione esplicita dell'utente, **NON nel mockup**. Nasconde tutte le label (nome app, label voci, nome utente); centra tassello logo, icone nav (l'highlight `#D6EAFB` della voce attiva resta), avatar e toggle (che mostra `chevron-right`). Lo stato è ricordato nell'istanza, **mai persistito su disco**.

**Tooltip in stato collassato — scelta**: si usa `QToolTip` nativo (`nav.setToolTip(label)` impostato solo quando collassata, azzerato quando espansa), **non** il componente `Tooltip` di questo pacchetto. Motivo: `Tooltip` è un'icona-info autosufficiente pensata per affiancarsi a una label in un form (è *lei* il trigger), non un decoratore hover per un widget arbitrario; per "hover su una voce → mostra la sua label" il tooltip nativo Qt è il fit corretto e non introduce un'icona estranea nella rail.

**Valori misurati dal Sketch (non assunzioni)**:
- **Colore icone nav**: **disaccoppiato dal testo** — icona attiva `#2563C9` (Blu), icona inattiva/hover `#3D9BE9` (Azzurro). Il testo invece è attivo `#163A6B` SemiBold / inattivo `#2E2E2E` Medium. (Correzione 2026-07-14: una prima versione assumeva erroneamente icona=colore testo; misurato lo stroke reale delle icone nel mockup.)
- **Divider tra le voci**: linea 1px `#E3EFFB` **tra ogni voce** nav (oltre a quelle sotto la Logo Row e sopra la User Row) — presente nel mockup, va renderizzata per ogni coppia di voci consecutive.

**Scarti / assunzioni dichiarate (non misurabili dal mockup)**:
- **Hover voce inattiva**: sfondo `#F7F9FC` (stesso grigio dei bottoni `SECONDARY`, nessun token nuovo) + cursore a mano. Non nel mockup, stesso principio già usato in `Button`/`TabBar`. La voce attiva ignora l'hover (mantiene `#D6EAFB`).
- **Colore icone toggle (chevron) e logout**: `#5B6472`, derivato (grigio di controllo, coerente con l'`x` di `Modal`); il mockup non lo specifica.
- **Highlight voce attiva a tutta larghezza** (nessun inset/radius): i token dati (pad-left, x label) sono paddings di contenuto, non citano margine/radius dell'highlight — reso a piena larghezza riga.
- **Logout in stato collassato**: nascosto (nella rail si centra solo l'avatar, come da elenco utente); resta raggiungibile riespandendo. Il toggle invece resta sempre visibile per poter riespandere.
- Toggle/logout sono bottoni piatti trasparenti (non la variante `Button.ICON_ONLY`, che avrebbe un box `#F7F9FC` fuori posto sullo sfondo della sidebar); hover leggero `#EFF4FA` — scelta di comportamento.

## AppShell / Finestra base

`AppShell(items: list[SidebarItem], app_name="LogiPlan", user_name="Davide", parent=None)` — sottoclasse di `QMainWindow` in `gui/main_window.py`: la shell dell'applicazione = `Sidebar` a sinistra + `QStackedWidget` a destra (sfondo area contenuti `#EAEAEA`). Titolo finestra "Gestionale Logistica", dimensione iniziale 1280×800. `MainWindow` resta come alias di `AppShell` (compatibilità con lo stub precedente).

```python
from gestionale_logistica.gui.main_window import AppShell
from gestionale_logistica.gui.components import SidebarItem

items = [SidebarItem("dashboard", "Dashboard", "layout-dashboard"), SidebarItem("ordini", "Ordini", "package")]
shell = AppShell(items)
shell.add_page("dashboard", pagina_dashboard_widget)
shell.add_page("ordini", pagina_ordini_widget)
shell.logoutRequested.connect(esegui_logout)
shell.show()
```

- Il costruttore crea internamente la `Sidebar` (esposta come `shell.sidebar`) con `items`/`app_name`/`user_name`.
- `shell.add_page(item_id, widget)` — registra la pagina per la voce `item_id`. La **prima** pagina aggiunta diventa quella mostrata all'avvio, con la relativa voce evidenziata.
- Il click su una voce (`sidebar.navigated`) cambia la pagina mostrata **e** mantiene sincronizzato l'highlight (`set_active`). Se una voce non ha una pagina registrata, l'highlight cambia comunque ma lo stack resta sulla pagina corrente.
- `shell.logoutRequested` — `Signal()`, inoltra il `logoutRequested` della Sidebar.

**Nota**: l'associazione voce↔pagina è 1:1 tramite l'`id` di `SidebarItem`; è responsabilità del chiamante usare gli stessi `id` in `SidebarItem` e in `add_page`.

## PageHeader

`PageHeader(title: str, actions: list[QWidget] | None = None, parent=None)` — sottoclasse di `QWidget`: barra di intestazione di una pagina, titolo a sinistra + slot azioni allineate a destra. Barra **trasparente** (nessun bordo/sfondo): sta in cima al contenuto di una pagina, sopra lo sfondo `#EAEAEA` dell'`AppShell`.

```python
from gestionale_logistica.gui.components import PageHeader, Button, ButtonVariant, load_lucide_icon

# pagina-lista: titolo + azione "Nuova ..." a destra
header = PageHeader("Squadre", [
    Button(ButtonVariant.SECONDARY_HEADER_ADD, "Nuova squadra", load_lucide_icon("circle-plus", "#2E2E2E", 15)),
])
# pagina senza azioni
header = PageHeader("Dashboard")
header.set_title("Dashboard aggiornata")  # API opzionale per cambiare titolo a runtime
```

- `actions`: lista di widget **arbitrari** decisi dal chiamante (tipicamente un `Button`), non solo il bottone "aggiungi" — `PageHeader` non conosce le azioni specifiche di ogni pagina. `None`/lista vuota = solo titolo.
- `header.set_title(str)` — cambia il titolo a runtime.
- Layout: `QHBoxLayout` con titolo, `addStretch(1)`, poi le azioni; gap 10px tra le azioni (`ACTIONS_GAP`, nel range 8–12px del mockup — non una misura pixel-precisa, non critico). `contentsMargins` a 0: il padding di pagina (~32px) lo mette il contenitore della pagina, non l'header.

**Valori esatti dal mockup**: titolo Inter **24px SemiBold (weight 600) `#2E2E2E`**. Nessun bordo/sfondo/ombra sulla barra.

## SearchField

`SearchField(placeholder: str = "Cerca...", parent=None)` — sottoclasse di `QWidget` in `gui/components/search_field.py`: campo di ricerca con **icona `search` a sinistra dentro il campo** + `QLineEdit`. **Niente label sopra** (a differenza di `TextField`).

```python
from gestionale_logistica.gui.components import SearchField

ricerca = SearchField(placeholder="Cerca dipendente, camion...")
ricerca.searchChanged.connect(lambda testo: ...)  # riquery/filtro lato chiamante
```

- `campo.value()` / `campo.set_value(str)` — API uniforme con `TextField`/`Select`.
- `campo.searchChanged` — `Signal(str)`, inoltra `QLineEdit.textChanged` a ogni digitazione.
- Larghezza **flessibile** (non fissata): nel mockup è 221px ma il componente si allarga a riempire lo spazio disponibile (`QLineEdit` con stretch nel layout interno).

**File a parte, non in `form_field.py` — motivo**: struttura diversa dagli altri field (niente label sopra, icona *dentro* il campo → un contenitore `QFrame` con la chrome + icona + `QLineEdit` senza bordo, invece di stilizzare direttamente il widget nativo con label sopra). La **chrome è però identica** a `TextField` e i token (`FIELD_BG`/`FIELD_BORDER`/`FIELD_RADIUS`/`FIELD_HEIGHT`/`FIELD_PADDING_H`/`FIELD_TEXT_COLOR`) e l'helper `_field_font` sono **importati** da `form_field.py`, non ridefiniti.

**Valori esatti dal mockup**: contenitore sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px, altezza 34px, padding orizzontale 12px; testo/placeholder Inter 13px/Medium `#5B6472` (stesso trattamento `QPalette::PlaceholderText` di `TextField`, così il placeholder non viene schiarito da Qt); icona `search` **`#8A93A0`** (= `LABEL_COLOR`), 16×16, a sinistra con gap 8px dal testo.

## EmptyState

`EmptyState(title: str, subtitle: str = "", icon_name: str = "inbox", parent=None)` — sottoclasse di `QWidget`: placeholder mostrato al posto di una lista/tabella quando non ci sono dati. Contenuto centrato orizzontalmente e verticalmente.

```python
from gestionale_logistica.gui.components import EmptyState

EmptyState("Nessuna squadra", "Le squadre che crei appariranno qui", "inbox")
EmptyState("Nessun risultato")                       # senza sottotitolo
EmptyState("Nessun ordine", icon_name="package")     # icona parametrica
```

- `icon_name`: nome icona Lucide (default `"inbox"`), deve esistere in `gui/assets/icons/`.
- `subtitle`: se vuoto, la seconda label non viene creata affatto (nessuno spazio riservato).
- Centratura: `QVBoxLayout` con `addStretch(1)` sopra e sotto, ogni elemento allineato `AlignHCenter`.

**Valori esatti dal mockup**: icona **40×40 colore `#B7BEC7`** (`load_lucide_icon(icon_name, "#B7BEC7", 40)`); titolo Inter **14px SemiBold `#8A93A0`**; sottotitolo (se presente) Inter **12px Medium `#B7BEC7`**; gap icona→titolo 16px, titolo→sottotitolo 8px.

## IconChip

`IconChip(icon_name: str, variant: IconChipVariant, size: int = 16, parent=None)` — sottoclasse di `QLabel`: chip circolare colorato con un'icona Lucide dentro. Verificato nel mockup su KPI Card e Activity Row della Dashboard (stesse 4 combinazioni colore in entrambi i contesti).

```python
from gestionale_logistica.gui.components import IconChip, IconChipVariant

IconChip("package", IconChipVariant.LIGHT_BLUE)
IconChip("triangle-alert", IconChipVariant.RED, size=16)
```

- `IconChipVariant`: `LIGHT_BLUE`/`BLUE`/`GREEN`/`RED` — 4 combinazioni (colore icona, colore sfondo chip) misurate nel mockup, non stimate: `LIGHT_BLUE` icona `#3D9BE9` bg `#D6EAFB`; `BLUE` icona `#2563C9` bg `#D6E4F7`; `GREEN` icona `#1E8E3E` bg `#DFF5E5`; `RED` icona `#C0392B` bg `#FBE4E1`. Esposte come `VARIANT_COLORS` in `icon_chip.py` se serve leggerle programmaticamente (es. per colorare un testo collegato, vedi `KpiCard`).
- Chip sempre circolare (`border-radius = size // 2`), sfondo e icona della stessa dimensione (`size`, default 16px come nel mockup) — non c'è un padding esplicito tra bordo del chip e glifo: i margini interni del grid Lucide 24×24 bastano a dare l'effetto visivo corretto.

**Personalizzazione**: nessun colore libero — solo le 4 varianti misurate. Se in futuro serve una quinta combinazione, va prima verificata nel mockup, non estrapolata.

## Scrollbar minimale: `MINIMAL_SCROLLBAR_QSS`

`MINIMAL_SCROLLBAR_QSS` (stringa QSS, in `gui/components/scroll_style.py`) — scrollbar sottile (6px), trasparente, **senza le frecce sopra/sotto** (`::add-line`/`::sub-line` a 0px), handle grigio traslucido (`rgba(138,147,160,0.35)`, riuso di `LABEL_COLOR` in trasparenza) che si scurisce leggermente in hover. Non nel mockup (nessuna scrollbar in un mockup statico) — richiesta esplicita dell'utente (2026-07-15, Dashboard) di uno stile minimale coerente con la palette dell'app invece della scrollbar di sistema.

```python
from gestionale_logistica.gui.components import MINIMAL_SCROLLBAR_QSS

scroll_area.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}")
```

- Va concatenata allo stylesheet del widget scrollabile (`QScrollArea`, o qualunque `QAbstractScrollArea`), non sostituita — le regole `QScrollBar` si applicano alla scrollbar interna del widget su cui è impostato lo stylesheet.
- **Nessuna variante**: un solo stile per tutta l'app, non parametrico — se in futuro serve una scrollbar diversa (es. più spessa per un'area con contenuto denso), va discusso con l'utente prima di introdurre un parametro.
- Usata per ora solo nell'area scrollabile di "Attività recente" nella Dashboard (vedi sotto); `Table` non ha ancora una propria area scrollabile (usa paginazione server-side) — se in futuro ne avrà una, riusare questo stesso stile.

## Icone: `load_lucide_icon`

Le icone del mockup sono icone [Lucide](https://lucide.dev) (libreria open-source, licenza ISC) — confermato per confronto diretto byte-a-byte tra gli SVG esportati da Sketch e gli SVG reali di Lucide, non per somiglianza visiva.

```python
load_lucide_icon("upload", "#2E2E2E", 12) -> QIcon
```

- `name`: nome icona Lucide (es. `"upload"`, `"calendar-plus"`, `"circle-plus"`, `"x"`) — deve esistere come file in `gui/assets/icons/<name>.svg`.
- `color`: colore esadecimale con cui ricolorare l'icona (le icone Lucide usano `stroke="currentColor"`, sostituito a runtime).
- `size`: dimensione di default suggerita — il rendering reale è vettoriale e ridisegnato da Qt a qualunque risoluzione/devicePixelRatio venga effettivamente richiesta (vedi nota sotto), quindi resta nitido anche su schermi Retina o se il chiamante chiede una `QIcon.pixmap()` a una dimensione diversa da `size`.

**Icone già vendorizzate**: `upload`, `calendar-plus`, `circle-plus`, `x`, `pencil`, `trash-2`, `chevrons-up-down`, `chevron-left`, `chevron-right`, `chevron-down`, `info`, `package`, `package-search`, `users`, `truck`, `circle-check-big`, `triangle-alert`, `calendar` (`gui/assets/icons/`). Le ultime 7 (2026-07-15, Dashboard) sono state identificate per struttura del path SVG (numero/ordine di `path`/`circle`/`polyline`/`rect`, non dal nome del bottone/etichetta) e verificate scaricando l'SVG reale da `lucide-static@1.24.0` (stessa versione già vendorizzata nel progetto) per confronto diretto degli elementi.

**Aggiungere una nuova icona**:
1. Trova l'icona nel mockup Sketch, esportala come SVG (`sketch.export(layer, { formats: ['svg'], ... })` via MCP, o manualmente da Sketch).
2. Identifica il nome Lucide corretto confrontando la struttura del path/le forme con `https://unpkg.com/lucide-static@latest/icons/<nome-ipotizzato>.svg` — **non indovinare dal nome del bottone/etichetta**, verificare sempre strutturalmente.
3. Scarica l'SVG vero da quell'URL (non l'export raster/vettoriale di Sketch) e salvalo in `gui/assets/icons/<nome-lucide>.svg`, mantenendo l'header di licenza ISC.
4. Usalo con `load_lucide_icon("<nome-lucide>", colore, size)`.

**Nota tecnica — perché non un semplice `QPixmap`**: la prima versione renderizzava l'SVG una volta sola in un `QPixmap` a dimensione fissa, che appariva sgranato su schermi Retina/HiDPI. `load_lucide_icon` ora restituisce un `QIcon` sostenuto da un `QIconEngine` custom (`_LucideIconEngine` in `icons.py`) che ridisegna l'SVG dal vettore ogni volta che Qt lo richiede, alla risoluzione effettiva — non un raster in cache. Qualunque nuovo loader di asset SVG dovrebbe seguire lo stesso pattern.

## AuthLogo

`AuthLogo(parent=None)` — sottoclasse di `QWidget`: tassello logo + "LogiPlan", centrati orizzontalmente, usati in cima alle 3 schermate di autenticazione (Login, Registrazione, Conferma OTP). Riusa l'helper/i token del logo della `Sidebar` (`_build_logo_badge`, `APP_NAME_COLOR`, `_make_font`) invece di ridefinirli — verificato via Sketch che sono lo stesso identico tassello (28×28 radius8 bg `#2563C9` + icona `route` bianca 16px, testo Inter 17px/Medium `#163A6B`), qui in riga centrata invece che nella logo row laterale.

```python
from gestionale_logistica.gui.components import AuthLogo
AuthLogo()
```

## LinkButton

`LinkButton(text, parent=None)` — sottoclasse di `QPushButton`: testo cliccabile in stile link, nessuna icona (unica istanza nel mockup: "Non hai ricevuto il codice? Invia di nuovo" nella schermata Conferma OTP). Valori misurati: Inter 12px/Medium, colore `#2563C9`, nessuno sfondo/bordo.

```python
from gestionale_logistica.gui.components import LinkButton
resend = LinkButton("Non hai ricevuto il codice? Invia di nuovo")
resend.clicked.connect(...)
```

- Usa il segnale `clicked` nativo di `QPushButton`, nessun segnale custom.
- **Stato hover** (non nel mockup): colore scurito (`_darken`, stesso helper di `Button`).
- **Nota**: solo la variante testo-senza-icona è implementata, perché è l'unica istanza usata finora. Se in futuro serve una variante con icona, va aggiunta come parametro opzionale ispezionando prima il mockup per quell'istanza specifica — non forzare/estrapolare da questa.

## OtpInput

`OtpInput(length=6, parent=None)` — sottoclasse di `QWidget`: N caselle a singolo carattere per un codice numerico (fonte: mockup Sketch, artboard "Conferma OTP"). Chrome della singola casella riusa i token di `TextField`/`Select` (`FIELD_BG`/`FIELD_BORDER`/`FIELD_RADIUS` da `form_field.py`); testo Inter 20px/Medium `#2E2E2E` (misurato).

```python
from gestionale_logistica.gui.components import OtpInput
otp = OtpInput()  # 6 caselle di default
otp.valueChanged.connect(lambda codice: ...)
otp.set_value("123456")
otp.clear()  # svuota e rifocalizza la prima casella
```

- `otp.value()` — stringa con le cifre digitate finora (può essere più corta di `length`).
- `otp.set_value(valore)` — popola le caselle (scarta silenziosamente i caratteri non numerici).
- `otp.valueChanged` — `Signal(str)`, emesso a ogni digitazione/incolla/`set_value`.
- `otp.clear()` — svuota tutte le caselle e rifocalizza la prima.

**Comportamento** (non verificabile in un mockup statico, standard atteso per un input OTP — stesso principio già usato per "click sul backdrop chiude" in `Modal`): digitare una cifra avanza automaticamente alla casella successiva; backspace su una casella vuota torna alla precedente; incollare una stringa multi-cifra la distribuisce sulle caselle a partire da quella su cui si incolla.

**Dimensioni della singola casella — assunzione dichiarata**: le 6 istanze nel mockup hanno larghezze leggermente incoerenti tra loro (37/37/30/30/30/30px, probabile artefatto di auto-layout in Sketch, non una misura intenzionale) — non pixel-perfect replicabile. Dimensione uniforme scelta in implementazione: 44×42px, gap 12px tra le caselle.

## Aggiungere un componente nuovo

Processo seguito finora per `Button` e `Card`, da ripetere per i prossimi (sidebar, tabella, ecc.):

1. **Cerca le istanze nel mockup Sketch** (via MCP: `run_code` con una ricerca per nome layer, es. `/sidebar|table/i`) — non assumere che un componente abbia un solo aspetto: cercare *tutte* le istanze in pagine diverse, perché spesso lo stesso nome ricorre con stili leggermente diversi.
2. **Estrai lo stile esatto** (fill, border, corner radius, font family/size/peso, padding, gap) via `run_code`/`get_layer_tree_summary`/`get_screenshot` — mai stimare a occhio da uno screenshot piccolo.
3. **Se trovi incoerenze tra istanze** (stesso componente con stili diversi in pagine diverse), non scegliere in autonomia quale sia quella "giusta": chiedere all'utente come trattarla (è un refuso nel mockup? è intenzionale e va esposto come parametro?).
4. **Se manca un dettaglio nel mockup** (es. stati hover/disabled non definiti), non inventare colori a caso: proporre una derivazione ragionevole (es. scurire/opacità) e farla approvare, oppure chiedere di definirla.
5. Implementa in `gui/components/<nome>.py`, esporta da `gui/components/__init__.py`.
6. Verifica visivamente con una finestra reale (non solo `pytest`) prima di darlo per concluso — uno script demo in una cartella temporanea è sufficiente, non serve committarlo.
7. **Documenta qui** (questo file): API, esempi d'uso, eventuali scarti intenzionali dal mockup e il perché.

**Trappola Qt — `QLabel` "stirata" mostra uno sfondo grigio non voluto** (trovata 2026-07-15 costruendo la Dashboard): un `QLabel` a cui è impostato solo `color:` nello stylesheet (senza `background:`) sembra trasparente finché resta piccola/aderente al testo — ma se viene aggiunta a un layout con **stretch factor** (es. `layout.addWidget(label, 1)`) o comunque si allarga oltre il proprio `sizeHint`, dipinge un riempimento grigio chiaro opaco su tutta la sua area, visibile perché lo stylesheet è attivo a livello app (`QStyleSheetStyle`). Non è mai capitato prima in questa libreria perché nessuna label esistente veniva mai stirata a riempire lo spazio disponibile. **Fix**: aggiungere sempre `background: transparent;` nello stylesheet di ogni `QLabel` di solo testo/icona che non deve avere un proprio sfondo — non fidarsi che "sembri già trasparente" in una preview con contenuto stretto, va verificato specificamente con una label stirata (es. dentro un `QHBoxLayout` con `addWidget(label, 1)`).

## Componenti pagina-specifici

Componenti la cui forma è ritagliata esattamente sul layout di **una** pagina (non genuinamente riusabili altrove) vivono in `gui/<pagina>/components/`, non in `gui/components/` — pattern deciso il 2026-07-15 costruendo la Dashboard. Stesso processo "Aggiungere un componente nuovo" sopra, stessa documentazione qui sotto, solo import path diverso.

**Dashboard** (`gui/dashboard/components/`, import `from gestionale_logistica.gui.dashboard.components import ActivityRow, KpiCard, PlanningDayCard`):

- **`KpiCard(value, label, icon_name, variant: IconChipVariant, trend: str | None = None, parent=None)`** — sottoclasse di `Card` (padding 20/18, spacing 12, riuso del preset già anticipato nella doc di `Card`): valore grande (Inter 28px Medium `#163A6B`) + trend opzionale in cima, `IconChip` + etichetta maiuscola (Inter 12px Medium `#5B6472`, uppercase forzato dal componente) sotto. Il testo del trend riusa il **colore icona della `variant`** (non un colore fisso positivo/negativo): nel mockup la card verde (consegnati) ha trend verde, la rossa (falliti) ha trend rosso — misurato, non assunto.
- **`PlanningDayCard(day_label, count_label, parent=None)`** — sottoclasse di `Card`/`QFrame`: etichetta giorno (Inter 12px SemiBold `#5B6472`) + badge pillola col conteggio (bg `#D6EAFB`, testo Inter 11px SemiBold `#2563C9`, radius 7 = altezza/2). Sfondo card `#F7F9FC`, nessun bordo, radius 10.
- **`ActivityRow(icon_name, variant: IconChipVariant, text, timestamp, parent=None)`** — riga: `IconChip` + testo evento (troncato con ellissi via `QFontMetrics.elidedText` a ogni `resizeEvent`, non nel mockup statico) + timestamp relativo a destra (Inter 12px Medium `#8A93A0`). Altezza fissa 52px. I divider 1px `#EDEFF3` tra le righe **non** sono nel componente: li disegna chi assembla la lista (stesso pattern già usato da `Modal`/`Table` per `DIVIDER_COLOR`, costante duplicata localmente per file, non condivisa).

**Pannello "Attività recente" — altezza elastica, non fissa (corretto 2026-07-15).** Il contenitore delle righe (`QScrollArea`, `MINIMAL_SCROLLBAR_QSS`) ha solo un **minimo** di 296px (5 righe, il budget del mockup) via `setMinimumHeight`, non un `setFixedHeight`: la card riceve stretch factor 1 nel layout verticale della pagina (`outer.addWidget(self._activity_card, 1)`, **senza** un `addStretch(1)` finale dopo) così si allarga a riempire lo spazio verticale disponibile su schermi grandi/fullscreen invece di lasciare un'area grigia vuota sotto la card, e si comprime fino al minimo (con scroll interno) su finestre piccole. **Prima versione era sbagliata**: altezza fissa via `setFixedHeight` + `outer.addStretch(1)` finale — lo stretch finale assorbiva tutto lo spazio extra come'area grigia morta invece di farlo usare dal contenuto. Se in futuro un'altra pagina ha un pannello a lista simile, riusare questo pattern (min-height + stretch sul contenitore, non fixed-height + stretch finale).

I dati reali (KPI aggregati, conteggio viaggi per i prossimi 7 giorni, feed attività) sono letti da `gui/dashboard/dashboard_data.py` — nessun RF1-RF19 definisce una Dashboard, le query aggregano dai modelli esistenti (vedi docstring del file per le assunzioni dichiarate: definizione di "disponibile", formula dei trend, provenienza dei 4 tipi di evento nel feed attività).
