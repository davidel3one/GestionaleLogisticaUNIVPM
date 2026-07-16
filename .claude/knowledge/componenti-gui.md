# Componenti GUI riusabili

Libreria di componenti PySide6 in `src/gestionale_logistica/gui/components/`, pensata per non riscrivere lo stesso widget/QSS in ogni pagina. Fonte di verità per ogni dettaglio visivo (colori, spaziature, radius, font, icone): il file `sketch/gui-design.sketch` — ogni componente qui è stato costruito ispezionando le istanze reali nel mockup, non a memoria/a occhio.

Import: `from gestionale_logistica.gui.components import AuthLogo, BooleanToggle, Button, ButtonVariant, Card, DatePicker, EmptyState, IconChip, IconChipVariant, LinkButton, Modal, MultiSelect, OtpInput, PageHeader, SearchField, Select, Sidebar, SidebarItem, TextField, Toast, ToastManager, ToastVariant, Tooltip, load_lucide_icon`.

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

**Cambiare l'etichetta a runtime**: `button.set_text("Nuovo testo")` (aggiunto 2026-07-16 per il footer di `CompositionCard` in Assistita, che rietichetta "Chiudi viaggio" in "Applica suggerimento e chiudi viaggio"). **Non** usare l'ereditato `QPushButton.setText()`: il testo visibile è disegnato da una `QLabel` interna, non dalla proprietà nativa `text` di `QPushButton` — chiamare `setText()` fa disegnare anche il testo nativo dello stile sopra/sotto la label custom, producendo testo sovrapposto/illeggibile (bug trovato costruendo Assistita).

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

`TabBar(labels: list[str], disabled: set[int] | None = None, parent=None)` — selettore di tab orizzontale con indicatore ad underline animato. Componente puramente visivo: **non** gestisce il contenuto delle pagine (niente `QStackedWidget` integrato) — chi lo usa si iscrive al segnale per cambiare il contenuto altrove.

```python
tabs = TabBar(["Ordini", "Esiti"], disabled={1})  # "Esiti" visibile ma non cliccabile
tabs.currentChanged.connect(lambda i: stacked_widget.setCurrentIndex(i))
```

- `labels`: qualunque numero di etichette (verificato nel mockup sia con 2 che con 3 tab, stesso stile).
- `disabled`: set di indici (0-based) da rendere non interattivi fin dalla costruzione — la tab resta **visibile e leggibile** (solo colore attenuato `#B0B6BF`), non sparisce dal layout come farebbe `QWidget.setDisabled`. Introdotto per Ordini: tab "Esiti" presente nel mockup ma non ancora collegata al lavoro RF15-RF18.
- `tabs.current_index` — property di sola lettura con l'indice della tab attiva.
- `tabs.set_current_index(i)` — imposta la tab attiva programmaticamente (solleva `ValueError` se fuori range); non ri-emette il segnale se `i` è già quello corrente.
- `tabs.currentChanged` — `Signal(int)`, emesso quando l'utente clicca una tab diversa (o quando cambia via `set_current_index`) — una tab disabilitata non emette mai questo segnale.

**Personalizzazione**: nessun parametro di stile esposto oltre a `disabled` (colori/font/gap sono fissi, replicano il mockup) — se serve un aspetto visivo diverso, non forzare i valori interni: è una variante nuova da valutare con l'utente.

**Stato hover** (non nel mockup): colore testo intermedio tra attivo e inattivo (`#22344D`, media tra `#163A6B` e `#2E2E2E` — nessun colore estraneo alla palette) + cursore a mano, stesso principio già usato in `Button`.

**Stato disabilitato** (non nel mockup, nessun frame lo disegna): colore `#B0B6BF` derivato come via di mezzo verso il grigio neutro della palette, cursore a freccia invece che a mano, click ignorati silenziosamente (non solleva eccezioni, semplicemente non emette `clicked`/`currentChanged`).

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
| `LINK` | identificativi (`#1040`, `V-20260707-01`) | sempre blu `#2563C9`, SemiBold — visivo, e cliccabile con `ColumnDef.on_click: Callable[[dict], None]` opzionale (cursore a mano, apre es. un modale di dettaglio); senza `on_click` resta solo visivo come prima |
| `STATUS_BADGE` | stato con pillola colorata | mappatura valore→(bg,testo) tramite `ColumnDef.status_colors` (dict), unita a una palette di default già pronta per 7 valori comuni (`Consegnato`/`Attivo`→verde, `Fallito`→rosso, `In consegna`→ambra, `Da pianificare`→grigio, `Pianificato`/`Proposto`→blu) — valori non mappati cadono sul grigio neutro |
| `BOOLEAN_BADGE` | flag sì/no (es. certificazione gas, sponda idraulica) | vero→pillola grigia con `true_label` (default "Sì"); falso→testo semplice con `false_label` (default "No", usa "—" se serve) |
| `ACTIONS` | icone azione per riga | `ColumnDef.actions: list[RowAction]`, ciascuna con `icon_name` (nome icona Lucide, vedi sezione icone), `callback(row: dict)`, `color` opzionale, `tooltip` opzionale, `predicate: Callable[[dict], bool]` opzionale — non limitato a modifica/elimina |
| `CAPACITY_BAR` | percentuale + barra di riempimento (colonna "CAPACITÀ") | valore = `float` 0-100; renderizza etichetta `N%` (Inter 11px SemiBold `#8A93A0`, misurata) sopra una `ProgressBar` 70×6px (vedi `## ProgressBar`); il colore del fill dipende dalla percentuale — 3 soglie misurate sul mockup: `<80%` blu `#3D9BE9`, `80-90%` ambra `#B45309`, `≥90%` rosso `#C0392B` (campioni reali 30/45/68%→blu, 82%→ambra, 91%→rosso; le soglie tonde 80/90 sono la lettura più plausibile tra i campioni, non pixel-misurate) |

**Fix (2026-07-15) — azioni condizionali per riga**: aggiunto `RowAction.predicate` — se impostato, l'icona compare solo per le righe dove `predicate(row)` è `True` (le altre non la mostrano affatto, non solo disabilitata). Introdotto per Dipendenti: "elimina" (licenzia) visibile solo per righe non-Cessato, "ripristina" (`rotate-ccw`) visibile solo per righe Cessato — due `RowAction` sulla stessa colonna, mutuamente esclusive per stato riga, invece di un'unica icona che cambia comportamento. Stesso pattern riusato identico per Camion ("dismetti"/"ripristina" su Dismesso). **Superato in seguito** (vedi sotto, redesign azioni riga) — "modifica"/"elimina" sono diventati due azioni fisse (nessun `predicate`), la logica condizionale di stato è passata dentro il callback.

**Redesign (2026-07-15) — matita = cambia stato, cestino = soft-delete**: su richiesta esplicita dell'utente, il significato delle due icone standard è stato ridefinito uniformemente su tutti i domini (Dipendenti/Camion/Viaggi/Squadre): la matita ("modifica") non apre più un form di editing campi, cambia lo stato attivo/non-attivo della riga in entrambe le direzioni (il callback decide la direzione guardando `row["stato"]`: da attivo disattiva, da non-attivo riattiva - un'unica `RowAction` senza `predicate`); il cestino ("elimina") fa lo stesso soft-delete di sempre (licenzia_dipendente/disattiva_camion/annulla_viaggio/elimina_squadra - imposta lo stato a non-attivo, preserva i dati per lo storico RF8), **stessa identica chiamata che la matita farebbe cliccata su una riga attiva** - le due icone si sovrappongono deliberatamente su quella direzione, la matita in più copre anche il percorso inverso (riassumi/riattiva/ripristina) che il cestino non fa. **Non** un hard-delete: un tentativo precedente in questa stessa sessione aveva reso il cestino un hard-delete irreversibile (nuovi metodi `elimina_*_definitivamente` nei gestori, con guardia contro violazioni di integrità referenziale) poi corretto su richiesta esplicita dell'utente - quei metodi `elimina_*_definitivamente` restano nei gestori (testati, potenzialmente utili altrove) ma **non sono più raggiungibili dalla UI** delle 4 pagine con stato a due valori. Su Ordini (nessun modello a due stati, nessun soft-delete possibile) il cestino resta l'unica eccezione a hard-delete (`elimina_ordine_definitivamente`), la matita resta assente (vedi "Lavoro deliberatamente rimandato" più sotto). L'editing dei campi anagrafici (nome/cognome, targa/tipo, ecc.) non è più raggiungibile dalla UI: rimosso, non semplicemente nascosto.

**Redesign (2026-07-15) — `ColumnDef.on_click` sulla colonna LINK**: aggiunto per spostare un modale di dettaglio dall'icona matita (ora "cambia stato", vedi sopra) al click sull'identificativo della riga. Usato da Viaggi (il modale "Modifica date" si apre cliccando l'ID viaggio) e Squadre (il modale dettaglio si apre cliccando l'ID squadra).

**Redesign (2026-07-16) — `_Switch` rimosso, sostituito da due `RowAction` a icona**: su richiesta esplicita dell'utente ("non sporcare il codice con componenti della stessa famiglia"), il componente `_Switch`/`RowAction.is_switch`/`RowAction.switch_value` (widget dedicato disegnato a mano, unico uso: Attivo/Dismesso su Camion) è stato **rimosso interamente** da `table.py` (era del tutto inutilizzato altrove) e sostituito dallo stesso pattern già usato per "ripristina"/"annulla" e per il "+"/spunta verde di Viaggi: due `RowAction` sulla stessa colonna con `predicate` mutuamente esclusivi, stesso `callback`, **stessa icona per entrambi gli stati con solo il colore che cambia** (non due icone speculari diverse). Icona passata per due iterazioni prima di arrivare a quella attuale — `toggle-right`/`toggle-left` (prima scelta, non piaceva esteticamente) → `chevrons-down-up` (su richiesta di "due frecce verso il centro, una sotto l'altra" — corretta strutturalmente ma ancora non gradita) → **`arrow-left-right`** (attuale, su un'immagine di riferimento fornita dall'utente: frecce orizzontali sfalsate, non chevron verticali) — ogni cambio ha rimosso l'SVG precedente da `gui/assets/icons/` (nessun altro uso). Colori riusati identici dalla palette già esistente per il badge di stato (`DEFAULT_STATUS_BADGE_COLORS["Attivo"]` = `#1E8E3E` verde, `STATO_BADGE_COLORS[STATO_DISMESSO]` = `#BF392A` rosso, in `gui/pages/camion/__init__.py`), non ridefiniti. Nessun impatto sul componente `Table`/`RowAction` per le altre pagine: nessuna usava `is_switch`.

**Personalizzazione**: `ColumnDef.width` (larghezza fissa in px) oppure `ColumnDef.stretch` (fattore di stretch, colonne più larghe in proporzione) — non impostare entrambi sulla stessa colonna, `width` vince se presente. `status_colors` sulla singola colonna sovrascrive/estende la palette di default senza doverla ridefinire tutta.

**`CAPACITY_BAR`** (aggiunta 2026-07-16 costruendo Pianificazione — Automatica, "Proposed Trips Table"): era segnalata "fuori scope" in questo file finché la pagina non fosse stata costruita davvero — ora implementata. Nel mockup la colonna CAPACITÀ ha larghezza 90px; il chevron a destra della barra (affordance "espandi riga", nessun comportamento/modale specificato nel mockup) va aggiunto come colonna `ACTIONS` separata subito dopo, non fa parte di `CAPACITY_BAR`.

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

## ConfirmModal

`ConfirmModal(title, message, confirm_label="Elimina", cancel_label="Annulla", parent=None)` — sottoclasse di `Modal`: modale di conferma generico (messaggio + Annulla/azione), per operazioni che meritano un passaggio esplicito prima di eseguirle. **Non nel mockup Sketch** (nessuna RF/artboard lo definisce, verificato anche sul pdf di riferimento — nessuna pagina delle 22 mostra un dialogo di conferma eliminazione): introdotto su richiesta esplicita dell'utente (2026-07-16) per "elimina camion/dipendente", che prima procedeva silenziosamente al click sul cestino.

```python
modale = ConfirmModal(
    "Elimina camion",
    f"Sei sicuro di voler eliminare il camion {riga['targa']}? Verrà segnato come dismesso...",
)
modale.confirmed.connect(lambda: esegui_eliminazione(riga))
modale.show_over(self)
```

- `modale.confirmed` — `Signal()`, emesso **solo** se l'utente clicca il bottone di conferma (non su Annulla/X/backdrop/ESC, che chiudono senza emettere nulla, ereditato da `Modal`). Il modale si chiude da solo in entrambi i casi — il chiamante non deve chiamare `close()`.
- Bottone di conferma in `ButtonVariant.PRIMARY` (blu), **non** una variante rossa/distruttiva: nessuna variante del genere esiste in `Button`, e introdurne una solo per questo caso sarebbe una deviazione dallo stile già stabilito (ogni altro modale di conferma del sito — Aggiungi/Modifica/Salva — usa lo stesso PRIMARY blu), non una scelta più coerente. Stessa larghezza 440px per ogni istanza (non misurata, scelta nel range delle altre due famiglie 560/900 già usate da `Modal`, più stretta perché il contenuto è solo una frase).
- Uso attuale: cestino su Camion, Dipendenti, Ordini (tab Ordini) e Ordini (tab Esiti) — `_elimina_riga`/`_elimina_esito` apre il modale, `_conferma_elimina_riga`/`_conferma_elimina_esito` esegue l'azione vera solo se `confirmed` viene emesso. **Camion/Dipendenti: soft-delete "vero"** (`elimina_camion`/`elimina_dipendente`, nuovo campo `Camion.flg_eliminato`/`Dipendente.flg_eliminato` in `database/models.py`) — passato per due iterazioni su richiesta esplicita dell'utente (2026-07-16): prima corretto da soft (`disattiva_camion`/`licenzia_dipendente`, che lasciava la riga visibile con badge Dismesso/Cessato) a hard-delete (`elimina_camion_definitivamente`/`elimina_dipendente_definitivamente`), poi l'utente ha chiesto lo **stesso risultato osservabile ma via soft-delete** invece di hard: la riga resta a database (RF8, integrità referenziale sempre garantita) ma è esclusa incondizionatamente da `visualizza_camion`/`visualizza_dipendenti`, anche scegliendo esplicitamente il filtro Stato Dismesso/Cessato — diverso da quel filtro, che nasconde solo di default (`## visualizza_dipendenti`/`## visualizza_camion` in `gestore_dipendenti.py`/`gestore_camion.py`). Funziona sia che la risorsa sia Attiva sia che sia già Cessata/Dismessa (nessun errore "già licenziato/dismesso"); rifiuta solo se la risorsa ha fatto parte di una squadra — non più necessario per l'integrità referenziale (la riga non sparisce), mantenuto solo per **non cambiare il risultato osservabile** rispetto all'hard-delete precedente, su richiesta esplicita. Gli hard-delete (`elimina_camion_definitivamente`/`elimina_dipendente_definitivamente`) restano nel backend, testati, ma senza più un punto d'ingresso GUI (stesso stato già accettato altrove in questo file per `modifica_date_viaggio`). **Migrazione**: `create_all()` non altera tabelle già esistenti — un DB `gestionale.db` pre-esistente va migrato a mano (`ALTER TABLE ... ADD COLUMN flg_eliminato BOOLEAN NOT NULL DEFAULT 0`) prima che l'app possa avviarsi contro di esso; non fatto automaticamente su richiesta dell'utente (schema aggiunto solo al modello). **Ordini/Esiti: hard-delete già esistente** (`elimina_ordine_definitivamente`/`elimina_esito`, invariati, solo la conferma è nuova). Non ancora esteso a Squadre/Viaggi (fuori scope della richiesta che l'ha introdotto, non testato lì).

## TextField

`TextField(label: str, placeholder: str = "", password: bool = False, validator: QValidator | None = None, parent=None)` — sottoclasse di `QWidget`: label sopra (obbligatoria) + `QLineEdit` sotto, chrome del mockup (stato chiuso, unico stato disegnato). `validator` (es. `QIntValidator`/`QDoubleValidator`/`QRegularExpressionValidator`) è opzionale, applicato all'input interno — nessun campo numerico/orario dedicato in libreria, per input vincolati si estende `TextField` con un validatore invece di ridigitare la chrome.

```python
TextField("Capacità (kg)", placeholder="es. 1200")
TextField("Targa", placeholder="es. AB123CD")
TextField("Ore di lavoro", placeholder="es. 8", validator=QDoubleValidator(0.5, 24.0, 1))
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

**`label` opzionale (aggiunta 2026-07-16 costruendo la Composizione Card di Pianificazione)**: `label` di default è `""` — se falsy, la riga della label sopra non viene creata affatto (nessuno spazio riservato, stesso principio di `EmptyState.subtitle`). Serve al campo "Aggiungi ordine" della Composizione Card (Pianificazione — Manuale/Assistita), l'unica istanza nel mockup di un `Select` senza etichetta sopra. Tutte le altre istanze esistenti continuano a passare una label e restano invariate.

**Assunzioni segnalate esplicitamente (non verificate nel mockup, che mostra solo lo stato chiuso)**:
- **Colore dell'icona chevron**: `#5B6472`, riusato dal testo del campo — il mockup non specifica un colore diverso per l'icona, quindi si riusa quello del testo come assunzione più sicura invece di introdurre un colore non misurato.
- **Popup delle opzioni**: nessun frame del mockup disegna il Select aperto. Per coerenza con gli altri componenti già fatti, il popup (`QMenu`) è stilato con: sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px (stessi token del resto), voce selezionata/hover con sfondo `#F7F9FC` (lo stesso grigio riusato per lo sfondo dei bottoni `SECONDARY` in `button.py`, per non introdurre un token nuovo), testo voci Inter 13px/Medium `#5B6472`. Scelta di implementazione non verificata, analoga a come `Modal` documenta "click sul backdrop chiude" come comportamento standard non nel mockup statico.

**Nota storica**: nella prima iterazione Multiselect e Date Picker erano stati rimandati (nessun frame del mockup li mostra aperti). L'utente ha poi deciso esplicitamente come implementarli senza aggiornare il mockup — vedi `## DatePicker` e `## MultiSelect` più sotto: non sono assunzioni di questa libreria, sono scelte confermate dall'utente.

**`compact` (aggiunta 2026-07-16, fix di allineamento segnalato dall'utente)**: `compact: bool = False`. Se `True`, la riga della label sopra non viene creata (come `label=""`) MA la label non sparisce — si sposta dentro il box, testo `"Label: valore"` su una sola riga, stessa altezza 34px di `TextField`/`SearchField`. Uso: i `Select` delle righe **Filtri** (Stato/Tipo/Squadra/Cert. gas/Sponda idraulica su Ordini/Dipendenti/Camion/Squadre/Viaggi) — verificato pixel per pixel su `gui-design.pdf` (pagine Ordini/Dipendenti/Camion/Squadre/Viaggi): li' il filtro non ha mai una label separata sopra, a differenza di ogni `Select` in un form/modale (es. "Camion" in "Aggiungi squadra", pagina 21), che restano invariati con `compact=False` (default). Prima di questa fix i filtri riusavano lo stesso `Select` dei form (label sopra) mentre `SearchField` accanto non ha mai avuto una label — risultato: righe Filtri con altezze disallineate tra il campo di ricerca e i Select, bug reale non un'assunzione. Vedi anche `DateFilterField` (`## DatePicker`) per lo stesso trattamento sul filtro Data.

**Fix (2026-07-15) — testo invisibile/troncato nella casella chiusa**: `_SelectBox` (usata da `Select` e `MultiSelect`) non aveva l'override di `sizeHint()` — `QPushButton.sizeHint()` di default lo calcola da `text()`/`icon()` propri (entrambi vuoti: il contenuto vero vive nel layout interno con `text_label` + icona), risultando in un box molto più stretto (es. 50px) di quanto il contenuto richieda davvero (es. 137px per "In viaggio"), che tronca/nasconde il testo in qualunque layout che non forzi una larghezza esplicita. Aggiunto `sizeHint() -> self.layout().sizeHint()`, stesso pattern già usato da `Button` per lo stesso identico motivo (vedi sopra). Segnalato da un bug reale su `gui/pages/dipendenti.py` ("le squadre/gli stati non si vedono nel riquadro"), poi ritrovato identico anche su Camion, Viaggi e Squadre.

## EditableSelect

`EditableSelect(label: str, options: list[str], placeholder: str = "", parent=None)` — sottoclasse di `QWidget` in `form_field.py`: campo con label sopra che permette sia di scegliere un'opzione esistente sia di digitarne una nuova al volo. Unica istanza: "Negozio partner" del modale Importa CSV (`import_csv_modal.py`) — non nel mockup (nessun frame disegna questo campo), decisione esplicita dell'utente di poter creare un valore nuovo oltre a scegliere tra quelli già visti (`GestoreLogistica.elenco_negozi_partner()`).

```python
from gestionale_logistica.gui.components import EditableSelect
campo = EditableSelect("Negozio partner", ["Unieuro Ancona", "MediaWorld Bari"], placeholder="Scegli o scrivi un nuovo negozio")
campo.valueChanged.connect(...)
campo.value()          # str, testo corrente (strip)
campo.set_value("...") # programmatico: seleziona se in elenco, altrimenti lo scrive come testo libero
```

Implementato con `QComboBox` nativo Qt editabile (non il popup custom `QMenu` di `Select`/`MultiSelect`, che non supporta l'editing testuale) — solo il chrome del campo chiuso replica gli stessi token (`FIELD_BG`/`FIELD_BORDER`/`FIELD_RADIUS`/`FIELD_HEIGHT`) del resto della libreria; la freccia del drop-down resta quella nativa Qt (avrebbe richiesto un asset SVG statico su disco per sostituirla via QSS, fuori scope per un campo assente dal mockup).

**Completamento a popup filtrato (2026-07-16, richiesta esplicita dell'utente)**: di default un `QComboBox` editabile usa `QCompleter` in modalità `InlineCompletion` (un solo suggerimento inline, nessuna lista). Qui il completer è riconfigurato in `PopupCompletion` con `filterMode=Qt.MatchContains`: mentre si digita appare un popup con **tutte** le opzioni che contengono il testo (non solo quelle che iniziano per — utile perché i negozi combinano catena+città, es. "Unieuro Ancona", cercabile per l'una o l'altra), cliccabili senza scrivere il nome per intero. Se il testo digitato coincide (case-insensitive) con un'opzione già in elenco, Invio la sostituisce col valore canonico salvato — comportamento nativo di `QComboBox` editabile, nessun codice scritto per ottenerlo. Il popup del completer è un `QAbstractItemView` distinto dal dropdown nativo del combo (quello aperto cliccando la freccia, con tutte le opzioni non filtrate) — stilati entrambi con lo stesso corpo QSS condiviso (`_item_view_qss()`, stessi token `FIELD_BG`/`FIELD_BORDER`/`FIELD_RADIUS`/`POPUP_HOVER_BG`/`FIELD_TEXT_COLOR`) più `MINIMAL_SCROLLBAR_QSS` (altrimenti una lista lunga mostrerebbe la scrollbar di sistema, stonata rispetto al resto dell'app).

## BooleanToggle

`BooleanToggle(label: str, parent=None)` — sottoclasse di `QWidget`: label sopra + due pillole affiancate "Sì"/"No" (etichette fisse, **non** un segmented control generico a N opzioni — nel mockup è specificamente un toggle booleano).

```python
sponda = BooleanToggle("Sponda idraulica")
sponda.valueChanged.connect(...)
```

- `toggle.value()` — `bool` (default `False`, cioè "No" selezionato).
- `toggle.set_value(True | False)` — seleziona programmaticamente la pillola corrispondente.
- `toggle.valueChanged` — `Signal(bool)`, emesso al click su una pillola o a `set_value()` esplicito.

**Valori esatti dal mockup**: due pillole 56×34px, gap 8px, border-radius 17px (capsula, = altezza/2); testo in entrambi gli stati Inter 13px/Medium `#5B6472` (stesso colore, verificato — il mockup non differenzia il colore testo tra selezionato/non selezionato); label sopra Inter 11px/SemiBold `#8A93A0`, gap 4px.

**Fix (2026-07-15)**: colori di selezione invertiti su richiesta esplicita dell'utente rispetto alla prima misurazione dal mockup — stato **selezionato**: sfondo `#EAEAEA` (grigio), bordo 1px `#E5EAF0`; stato **non selezionato**: sfondo `#FFFFFF`, nessun bordo. Vale per ogni uso del componente (es. "Certificazione gas" in Dipendenti, "Sponda idraulica" in Camion), non solo per quello segnalato.

## DatePicker

`DatePicker(label: str, parent=None)` — sottoclasse di `QWidget`: label sopra + `_DateEditBox` (chrome flat condivisa con `DateFilterField`, wrapper attorno a un `QDateEdit` nativo con `calendarPopup=True`).

```python
data = DatePicker("Data consegna")
data.valueChanged.connect(...)
data.set_value(QDate(2026, 7, 11))
```

- `field.value()` — `QDate` (default: data odierna, `QDate.currentDate()`, comportamento nativo di `QDateEdit`).
- `field.set_value(QDate(...))` — imposta la data programmaticamente.
- `field.valueChanged` — `Signal(QDate)`, inoltra `QDateEdit.dateChanged`.
- Formato di visualizzazione: `dd/MM/yyyy` (costante `DATE_FORMAT` in `form_field.py`), coerente con gli esempi nel mockup ("11/07/2026", "14/10/2020").

**Decisione esplicita dell'utente (non un'assunzione)**: il calendario a comparsa è quello **nativo di Qt/OS**, non ridisegnato — nessuno stile del sistema di design applicato al popup del calendario in sé. Il chrome del campo chiuso è ristilizzato per combaciare con gli altri field: sfondo `#FFFFFF`, bordo 1px `#E5EAF0`, radius 9px, altezza 34px, testo Inter 13px/Medium `#5B6472` (stessi identici token/costanti di `TextField`/`Select`, nessun valore duplicato).

**Fix 2026-07-16 (bug segnalato dall'utente)**: il pulsantino calendario nativo di `QDateEdit` (freccia a destra) veniva disegnato dallo stile Qt/OS di default — un quadratino "primitivo" incoerente con il resto della UI, mentre il mockup (frame "Data Filter"/"Stato Filter", identiche) mostra la stessa chrome piatta di `Select`: solo testo + chevron vettoriale, nessun bottone visibile. Risolto in `_DateEditBox` (`form_field.py`): `QDateEdit::drop-down` reso trasparente e largo quanto la zona riservata (bordo/sfondo `none`/`transparent`), `QDateEdit::down-arrow` azzerata (`width/height: 0`, `image: none`), e un `QLabel` con `load_lucide_icon("chevron-down", ...)` sovrapposto sopra via posizionamento esplicito in `resizeEvent` (non `QStackedLayout`: in `StackAll` i widget aggiunti dopo il primo non venivano renderizzati nel test manuale). Il `QLabel` ha `WA_TransparentForMouseEvents` così i click passano al drop-down nativo sottostante (verificato: il calendario si apre ancora normalmente). Chrome condivisa tra `DatePicker` e `DateFilterField` tramite la classe `_DateEditBox`.

**`DateFilterField(parent=None)`** — sottoclasse di `_DateEditBox`, campo data compatto senza label sopra: testo `"Data: dd/MM/yyyy"` via `setDisplayFormat("'Data: 'dd/MM/yyyy")` sul suo `.input` (letterale tra apici singoli, feature nativa di `QDateEdit`, non un widget custom), larghezza fissa 200px. `field.value() -> QDate` / `field.set_value(QDate(...))` / `field.valueChanged: Signal(QDate)`. Nato dentro `gui/pianificazione/components/` per il filtro Data di Pianificazione — Automatica; **promosso a `gui/components/` (2026-07-16)** non appena si è presentata una seconda occasione di riuso identica: il filtro Data delle righe Filtri di Ordini/Dipendenti (dove presente)/Camion/Squadre/Viaggi aveva lo stesso identico bug di allineamento di `Select` senza `compact` (vedi sopra) — stesso percorso già fatto per `ProgressBar`. Import: `from gestionale_logistica.gui.components import DateFilterField` (anche `gui.pianificazione.components` continua a riesportarlo, per non rompere gli import esistenti li').

## MultiSelect

`MultiSelect(label: str, options: list[str], placeholder: str = "Seleziona...", parent=None, compact: bool = False)` — sottoclasse di `QWidget`: stessa chrome esterna chiusa di `Select` (riusa `_SelectBox`), popup con una `QCheckBox` per opzione invece di un `QAction` singola.

```python
giorni = MultiSelect("Giorni disponibili", options=["Lun", "Mar", "Mer", "Gio", "Ven"])
giorni.valueChanged.connect(...)
giorni.set_value(["Lun", "Mer"])
```

- `campo.value()` — `list[str]` (vuota finché nessuna opzione è selezionata).
- `campo.set_value(valori)` — imposta la selezione programmaticamente (filtra silenziosamente valori non presenti in `options`).
- `campo.valueChanged` — `Signal(list)`, emesso a ogni check/uncheck di una voce nel popup o a `set_value()` esplicito.
- Testo mostrato nel campo chiuso: `placeholder` (default `"Seleziona..."`) se vuoto, il nome dell'opzione se una sola selezionata, `"N selezionati"` se più di una — testo di sistema, non presente nel mockup.
- `compact=True` (2026-07-16, righe Filtri — stesso uso di `Select.compact`, tutti i filtri a scelta multipla lo passano): stesso identico comportamento di `Select(compact=True)`, niente label sopra, testo del box "Label: valore" — nessuna nuova chrome, riusa `_SelectBox` e la stessa regola di formattazione testo, solo applicata al riassunto multi-valore invece che al valore singolo.

**Decisione esplicita dell'utente (non un'assunzione)**: nessun frame del mockup mostra un multiselect aperto. Pattern "testo riassuntivo nel campo chiuso + popup con checkbox" scelto dall'utente in assenza di mockup, non dedotto. Il popup riusa `_build_popup_chrome` (helper condiviso, fattorizzato da `Select` invece di duplicare lo stesso QSS): sfondo `#FFFFFF`, bordo `#E5EAF0`, radius 9px, voce hover `#F7F9FC`, testo Inter 13px/Medium `#5B6472` — stessi token del popup Select. Le checkbox restano native Qt (`QCheckBox`), solo ricolorate/spaziate con lo stesso QSS delle voci del menu Select; il popup resta aperto tra un check e l'altro (comportamento standard di `QWidgetAction` con widget custom dentro un `QMenu`, necessario per selezionare più voci in sequenza).

**Filtri a scelta multipla (2026-07-16)**: tutte le Select delle righe Filtri (Dipendenti/Camion/Squadre/Viaggi/Ordini, incluso il tab Esiti) sono state convertite da `Select` a `MultiSelect(compact=True)`, su richiesta esplicita dell'utente — il componente esisteva già, non introdotto per l'occasione. Le voci sentinella "Tutti"/"Tutte" (`FILTRO_TUTTI`/`FILTRO_TUTTE_SQUADRE`/...) sono state **rimosse** dalla lista opzioni passata al widget: con `MultiSelect` il "nessun filtro" è nativamente la selezione vuota (l'utente deflagga tutto), a differenza di `Select` che aveva bisogno di una voce esplicita per tornare a "tutti" (nessun modo di deselezionare un `QAction` radio-like dal popup). Il backend (`GestoreDipendenti`/`GestoreCamion`/`GestoreSquadre`/`GestoreLogistica`/`GestoreRendicontazione`) resta compatibile con entrambe le forme: i parametri `filtro_stato`/`filtro_tipo`/`filtro_squadra`/`filtro_esito` accettano sia una stringa singola (retrocompatibilità con le chiamate esistenti/i test) sia una `list[str]` (piu' valori in OR); i filtri booleani (Cert. gas, Sponda idraulica) restano `bool | None` lato backend — la GUI converte la lista di etichette Sì/No selezionate in un singolo booleano (una sola etichetta selezionata) o `None` (zero o entrambe, equivale a "tutti").

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

**Valori esatti dal mockup**: popover sfondo `#EAEAEA`, radius 10px; testo Inter 12px/Medium `#2E2E2E`, padding 12px verticale / 16px orizzontale; icona trigger 18×18 (Lucide `info`, identificata per confronto strutturale dei path SVG, non a occhio); gap orizzontale 10px tra icona e popover, popover verticalmente centrato rispetto all'icona; nessuna freccia/puntatore verso l'icona (il popover nel mockup ha un solo figlio, il testo).

**Bordo 1px + ombra più marcata (2026-07-16, richiesta esplicita dell'utente, non nel mockup)**: il popover (`Popover.paintEvent`) aveva solo il fill arrotondato dipinto a mano (`NoPen`, nessun contorno) — ora un `QPen` 1px colore `POPOVER_TEXT_COLOR` (`#2E2E2E`, riusato) disegna anche il contorno, con il rettangolo inset di 0.5px per evitare che il tratto (centrato sul bordo) venga tagliato a metà dai limiti del widget. Reso "uniforme" perché `Popover` è un unico componente riusato sia da `Tooltip` (icona info) sia dall'hover di troncamento testo in `Table._ElidingLabel` — la modifica si applica automaticamente a entrambi. Ombra aumentata in coppia col bordo ("un po' di rialzo", scelta non misurata): `QGraphicsDropShadowEffect(color=#0000002E, offset=(0,12), blur=32)`, era `(color=#00000026, offset=(0,8), blur=24)`.

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

## LinkButton

`LinkButton(text: str, icon_name: str, parent=None)` — sottoclasse di `QPushButton` in `gui/components/link_button.py`: icona Lucide + testo in stile link (nessuno sfondo/bordo), usato per "Ripristina filtri" nelle Filter Card.

```python
link = LinkButton("Ripristina filtri", "rotate-ccw")
link.clicked.connect(self._ripristina_filtri)  # segnale nativo QPushButton, nessun segnale custom
```

**Verificato nel mockup**: presente identico (stesso font/colore) in più artboard con Filter Card, incluse "Camion", "Ordini", "Viaggi" e "Squadre" — non un elemento specifico di una sola pagina, lo stesso elemento ricorre ovunque c'è una lista filtrata. Da usare fin dall'inizio in ogni nuova pagina lista (non un workaround ad-hoc tipo opzione "Tutti" dentro le tendine).

**Valori esatti dal mockup**: icona 13×13, gap 6px dal testo, testo Inter-Medium 13px, colore `#2563C9` (stesso blu di `Button` PRIMARY) sia per icona che testo. Icona usata: `rotate-ccw`.

**Assunzione segnalata**: stato hover non disegnato nel mockup (solo a riposo) — derivato scurendo il colore del testo (stesso principio di `Button._darken`), non misurato.

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

- `IconChipVariant`: `LIGHT_BLUE`/`BLUE`/`GREEN`/`RED`/`AMBER` — combinazioni (colore icona, colore sfondo chip) misurate nel mockup, non stimate: `LIGHT_BLUE` icona `#3D9BE9` bg `#D6EAFB`; `BLUE` icona `#2563C9` bg `#D6E4F7`; `GREEN` icona `#1E8E3E` bg `#DFF5E5`; `RED` icona `#C0392B` bg `#FBE4E1`; `AMBER` icona `#B45309` bg `#FEF3C7`. Esposte come `VARIANT_COLORS` in `icon_chip.py` se serve leggerle programmaticamente (es. per colorare un testo collegato, vedi `KpiCard`).
- Chip sempre circolare (`border-radius = size // 2`), sfondo e icona della stessa dimensione (`size`, default 16px come nel mockup) — non c'è un padding esplicito tra bordo del chip e glifo: i margini interni del grid Lucide 24×24 bastano a dare l'effetto visivo corretto.

**`AMBER` (aggiunta 2026-07-16 per `Toast`)**: le prime 4 varianti erano tutte misurate su istanze reali di `IconChip` nel mockup (KPI Card/Activity Row Dashboard). `AMBER` è diversa: non esiste un'istanza `IconChip` ambra nel mockup, ma la coppia colore riusa 1:1 valori già misurati altrove nello stesso mockup per lo stesso stato semantico (`DEFAULT_STATUS_BADGE_COLORS["In consegna"]` in `table.py`, badge categoria "Big"/"Certificazione Gas" in `CompositionCard`) — non è un'estrapolazione a occhio, è lo stesso colore verificato applicato a un quinto rendering circolare.

**Personalizzazione**: nessun colore libero — solo le varianti elencate sopra. Se in futuro serve una combinazione nuova non riconducibile a un colore già misurato altrove nel mockup, va prima verificata come istanza `IconChip` dedicata, non estrapolata.

## Toast

`Toast(variant: ToastVariant, title: str, message: str = "", duration_ms: int = 4500, parent=None)` — singolo banner di notifica non bloccante; `ToastManager(parent: QWidget)` — overlay che impila i `Toast` in alto a destra del `parent` e li gestisce (mostra/rimuove/riposiziona al resize). **Non è un elemento del mockup Sketch** — nessuna istanza "Toast"/"Notification" nel file (verificato via MCP su tutte le pagine, unico match per "alert" è l'"Alert Box" testuale già documentato in `CompositionCard`). Stile/comportamento gated esplicitamente con l'utente il 2026-07-16 in assenza di mockup, seguendo il processo "Aggiungere un componente nuovo".

```python
from gestionale_logistica.gui.components import ToastManager, ToastVariant

toasts = ToastManager(central_widget)   # una sola istanza per finestra/pagina che deve notificare
toasts.show_success("Ordine creato", "Il viaggio è stato pianificato con successo.")
toasts.show_error("Import fallito", "Il file CSV contiene righe non valide.")
toasts.show_warning("Capacità quasi esaurita", "Il camion è al 92% della portata massima.")
toasts.show_info("Sincronizzazione in corso")                      # senza messaggio
toasts.show_toast(ToastVariant.SUCCESS, "Salvato")                 # forma esplicita, equivalente a show_success
```

- `ToastVariant`: `SUCCESS`/`ERROR`/`WARNING`/`INFO` — le 4 richieste dall'utente.
- `manager.show_success/show_error/show_warning/show_info(title, message="", duration_ms=4500)` — scorciatoie su `show_toast(variant, ...)`, tutte restituiscono il `Toast` creato.
- `message` opzionale: se vuoto, il toast mostra solo il titolo (nessuna riga vuota riservata) — stesso principio di `EmptyState.subtitle`.
- `duration_ms`: `0` disattiva l'auto-dismiss (il toast resta finché non si clicca la X) — non usato dalle scorciatoie `show_*`, ma disponibile passandolo esplicitamente.
- Chiusura: timer (`QTimer.singleShot`) **e** bottone X sempre presenti insieme — deciso esplicitamente dall'utente (non "solo auto" o "solo manuale").
- **Barra di countdown** (aggiunta 2026-07-16, richiesta esplicita dell'utente): striscia 3px in basso, colore accento della variante, che si svuota da sinistra a destra in modo lineare per tutta la durata di `duration_ms` — sincronizzata allo stesso valore usato da `QTimer.singleShot`, quindi arriva a zero esattamente quando il toast scompare. Implementata con lo stesso pattern già usato in `TabBar` per l'underline animato: proprietà Qt (`Property(float, ...)`) + `QPropertyAnimation`, qui con `QEasingCurve.Linear` (non `OutCubic` come `TabBar`: è un countdown, deve procedere a velocità costante, non con accelerazione/decelerazione). Disegnata con `painter.setClipPath` sulla stessa `QPainterPath` arrotondata dello sfondo, così i bordi la "tagliano" automaticamente senza ricalcolare a mano gli angoli in base alla larghezza residua. Assente se `duration_ms=0` (nessun countdown da mostrare per un toast a chiusura solo manuale). **Nessun pausa-on-hover**: il countdown continua anche col mouse sopra il toast — scelta minimale, non richiesta; se in futuro serve, va aggiunta esplicitamente.
- `ToastManager` si registra come `eventFilter` sul `parent` per riposizionarsi al resize (stesso pattern di `Modal.show_over`, qui attaccato una volta sola alla costruzione invece che per singola apertura) e impila i toast con `QVBoxLayout` (nuovi si aggiungono in fondo, sotto quelli già visibili); alla chiusura di un toast (timer o X) gli altri risalgono automaticamente.

**Stile visivo — banner a tinta piena** (scelto dall'utente tramite screenshot di riferimento, poi adattato alla palette del progetto): sfondo colorato pieno pastello (non card bianca con accento), `IconChip` della variante a sinistra, titolo (Inter 13px SemiBold) + messaggio opzionale (Inter 12px Medium) impilati, bottone chiusura piatto trasparente (non `Button.ICON_ONLY`: il suo box grigio fisso `#F7F9FC` stonerebbe sopra uno sfondo colorato, stesso motivo già documentato per i pulsanti di `Sidebar`). Titolo e messaggio usano **lo stesso colore accento saturo** della variante (non testo nero/grigio neutro come nel riferimento fornito dall'utente): scelta per restare coerente con il linguaggio già stabilito nel progetto per gli sfondi tinta (`STATUS_BADGE`/`CATEGORIA_BADGE`, sempre accento+sfondo della stessa famiglia), non con il design system esterno dello screenshot.

**Palette per variante — interamente riusata, nessun colore nuovo**:

| `ToastVariant` | Icona Lucide | Accento (testo/icona) | Sfondo | Fonte del colore |
|---|---|---|---|---|
| `SUCCESS` | `circle-check-big` | `#1E8E3E` | `#DFF5E5` | `IconChipVariant.GREEN` |
| `ERROR` | `circle-x` | `#C0392B` | `#FBE4E1` | `IconChipVariant.RED` |
| `WARNING` | `triangle-alert` | `#B45309` | `#FEF3C7` | `IconChipVariant.AMBER` (vedi sopra) |
| `INFO` | `info` | `#3D9BE9` | `#D6EAFB` | `IconChipVariant.LIGHT_BLUE` |

**Icona `circle-x` — nuova, non nel mockup** (serviva un glifo distinto da `triangle-alert` per non usare la stessa icona per WARNING ed ERROR differenziati solo dal colore): scaricata direttamente da `lucide-static@1.24.0` (stessa versione già vendorizzata), non estratta dal mockup — stesso principio già seguito per dettagli assenti nel mockup (es. comportamento hover di `Tooltip`).

**Valori scelti in implementazione (nessuno misurabile nel mockup, dichiarati esplicitamente)**: larghezza fissa 360px; radius 14px (stesso token `CARD_RADIUS` di `Modal`, famiglia "elemento flottante arrotondato" invece di introdurre un radius nuovo); padding 16px orizzontale/14px verticale, gap 12px tra icona/testo; posizione overlay: margine 24px da top e da destra rispetto al `parent`, gap 12px tra toast impilati.

**Nessuna ombra** (scarto rispetto a un primo tentativo): una prima versione aggiungeva un `QGraphicsDropShadowEffect` (riuso del token ombra di `Tooltip`, `color=#00000026, offset=(0,8), blur=24`) per dare rilievo al banner. Segnalato dall'utente un alone grigio visibile proprio agli angoli arrotondati in basso — l'offset verticale porta l'ombra a "uscire" dalla sagoma colorata sui lati dove il bordo curva verso l'interno, leggibile come artefatto piuttosto che come elevazione. Rimossa: il riferimento visivo originale fornito dall'utente era comunque un banner piatto, senza ombra.

**Nota — nessuna animazione**: né ingresso né uscita sono animati (coerente con la baseline non-animata degli altri componenti — `Modal` non anima apertura/chiusura; solo `TabBar` anima, su richiesta esplicita per quel caso specifico). Se in futuro serve un fade/slide, va deciso esplicitamente, non aggiunto di default.

## Scrollbar minimale: `MINIMAL_SCROLLBAR_QSS`

`MINIMAL_SCROLLBAR_QSS` (stringa QSS, in `gui/components/scroll_style.py`) — scrollbar sottile (6px), trasparente, **senza le frecce sopra/sotto** (`::add-line`/`::sub-line` a 0px), handle grigio traslucido (`rgba(138,147,160,0.35)`, riuso di `LABEL_COLOR` in trasparenza) che si scurisce leggermente in hover. Non nel mockup (nessuna scrollbar in un mockup statico) — richiesta esplicita dell'utente (2026-07-15, Dashboard) di uno stile minimale coerente con la palette dell'app invece della scrollbar di sistema.

```python
from gestionale_logistica.gui.components import MINIMAL_SCROLLBAR_QSS

scroll_area.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} {MINIMAL_SCROLLBAR_QSS}")
```

- Va concatenata allo stylesheet del widget scrollabile (`QScrollArea`, o qualunque `QAbstractScrollArea`), non sostituita — le regole `QScrollBar` si applicano alla scrollbar interna del widget su cui è impostato lo stylesheet.
- **Nessuna variante**: un solo stile per tutta l'app, non parametrico — se in futuro serve una scrollbar diversa (es. più spessa per un'area con contenuto denso), va discusso con l'utente prima di introdurre un parametro.
- Usata per ora solo nell'area scrollabile di "Attività recente" nella Dashboard (vedi sotto); `Table` non ha ancora una propria area scrollabile (usa paginazione server-side) — se in futuro ne avrà una, riusare questo stesso stile.

## ProgressBar

`ProgressBar(percent: float, width=70, height=6, fill_color="#3D9BE9", parent=None)` — sottoclasse di `QWidget` in `gui/components/progress_bar.py`: barra track+fill disegnata con `QPainter` (non layout absolute). Nata dentro `table.py` per la colonna `CAPACITY_BAR` (2026-07-16) e promossa qui componente condiviso quando è servita una seconda istanza identica: le barre Peso/Volume della Composizione Card (Pianificazione — Manuale/Assistita) hanno stessi colori/stile.

```python
from gestionale_logistica.gui.components import ProgressBar
ProgressBar(45.0)                                   # 70x6, blu di default
ProgressBar(68.0, width=350, height=8)               # barra larga (Composizione Card)
ProgressBar(91.0, fill_color="#C0392B")               # colore esplicito (soglie capacità, vedi Table)
```

**Valori esatti dal mockup**: track `#EAEAEA`, fill `#3D9BE9` (default), radius = altezza/2 (capsula). Due dimensioni verificate: 70×6px (colonna CAPACITÀ) e 350×7-8px (barre Peso/Volume Composizione Card — 7 vs 8px sono varianti minori tra istanze del mockup, non critico). Il colore del fill **non** è un parametro fisso del componente: chi lo usa decide (soglie per `Table.CAPACITY_BAR`, sempre blu per le barre Peso/Volume).

`bar.set_percent(percent, fill_color=None)` — aggiorna percentuale (e opzionalmente colore) a runtime senza ricreare il widget, con un semplice `update()`/repaint.

## LoadingSpinner

`LoadingSpinner(size=24, parent=None)` — sottoclasse di `QWidget` in `gui/components/loading_spinner.py`: cerchio indeterminato animato (arco che ruota), disegnato con `QPainter`+`QTimer` (nessuna dipendenza da animazioni Qt). Aggiunto 2026-07-16 per il pulsante "Calcola piano" di Pianificazione — Automatica (RF13): il calcolo gira in background fino a RNF4=3min senza una percentuale nota, quindi un indicatore indeterminato (non una `ProgressBar` con `%` finta) è la scelta corretta.

```python
from gestionale_logistica.gui.components import LoadingSpinner
LoadingSpinner()      # 24x24, arco blu #2563C9 su track #EAEAEA
LoadingSpinner(32)    # dimensione esplicita
```

**Non nel mockup Sketch**: nessun artboard modella uno stato di caricamento (verificato via `get_document_info`/`get_layer_tree_summary` sull'artboard "Pianificazione" — la Proposed Trips Table è disegnata solo nello stato "risultato già calcolato"). Colori derivati dalla Palette invece che misurati: track `#EAEAEA` (stesso token di `ProgressBar`), arco Blu `#2563C9` (colore di `Button` PRIMARY, non l'Azzurro `#3D9BE9` di `ProgressBar`) per leggere come "azione primaria in corso" coerentemente col bottone che l'ha avviata.

**Uso in `automatica_tab.py`**: `_show_loading_state()` sostituisce l'area risultati (stesso `_results_container` di `_show_empty_state`) con `LoadingSpinner(32)` + testo "Calcolo del piano in corso…" centrati — stessa struttura/colore/font di `EmptyState` (icona + titolo `#8A93A0` 14px/600), solo con lo spinner al posto dell'icona statica. Il bottone "Calcola piano" mantiene in aggiunta il proprio testo di stato ("Calcolo in corso…", preesistente) e si disabilita insieme ad "Annulla"/"Applica piano" per non lasciare azioni attive su un piano che sta per essere sostituito.

## Icone: `load_lucide_icon`

Le icone del mockup sono icone [Lucide](https://lucide.dev) (libreria open-source, licenza ISC) — confermato per confronto diretto byte-a-byte tra gli SVG esportati da Sketch e gli SVG reali di Lucide, non per somiglianza visiva.

```python
load_lucide_icon("upload", "#2E2E2E", 12) -> QIcon
```

- `name`: nome icona Lucide (es. `"upload"`, `"calendar-plus"`, `"circle-plus"`, `"x"`) — deve esistere come file in `gui/assets/icons/<name>.svg`.
- `color`: colore esadecimale con cui ricolorare l'icona (le icone Lucide usano `stroke="currentColor"`, sostituito a runtime).
- `size`: dimensione di default suggerita — il rendering reale è vettoriale e ridisegnato da Qt a qualunque risoluzione/devicePixelRatio venga effettivamente richiesta (vedi nota sotto), quindi resta nitido anche su schermi Retina o se il chiamante chiede una `QIcon.pixmap()` a una dimensione diversa da `size`.

**Icone già vendorizzate**: `upload`, `calendar-plus`, `circle-plus`, `x`, `pencil`, `trash-2`, `chevrons-up-down`, `arrow-left-right`, `chevron-left`, `chevron-right`, `chevron-down`, `info`, `package`, `package-search`, `users`, `truck`, `circle-check-big`, `triangle-alert`, `calendar`, `eye`, `circle-x` (`gui/assets/icons/`). Le 7 tra `info` e `calendar` (2026-07-15, Dashboard) sono state identificate per struttura del path SVG (numero/ordine di `path`/`circle`/`polyline`/`rect`, non dal nome del bottone/etichetta) e verificate scaricando l'SVG reale da `lucide-static@1.24.0` (stessa versione già vendorizzata nel progetto) per confronto diretto degli elementi. `eye` (2026-07-16, tab Esiti — azione "modifica" su una riga Fallito, al posto di `pencil`) e `circle-x` (2026-07-16, `Toast`) non vengono da un artboard Sketch — scaricate direttamente dallo stesso `lucide-static@1.24.0` per coerenza di stile con le altre (vedi `## Toast` per `circle-x`). `arrow-left-right` (2026-07-16, Camion — icona finale dopo due iterazioni, `toggle-right`/`toggle-left` → `chevrons-down-up` → questa, tutte rimosse via via, vedi "Redesign (2026-07-16)" sopra) idem.

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

## Lacune candidate nella libreria (non ancora verificate, da controllare quando servono davvero)

Annotate durante la pianificazione delle pagine Dipendenti/Camion/Ordini/Viaggi (2026-07-15), non
ancora affrontate — segnate qui perché non spariscano con la fine di quella sessione:

- **Errore di validazione inline su un campo form** (es. "Peso massimo" del modale Camion — Aggiungi
  digitato non numerico): nessun componente esistente mostra un messaggio di errore sotto/accanto
  a un `TextField`. Prima di inventare una label rossa ad-hoc dentro una pagina, verificare contro
  Sketch se esiste già una convenzione visiva per questo caso (in questo mockup o in altri form,
  es. Autenticazione) — se sì, va costruito come componente riusabile seguendo il processo qui
  sotto, non duplicato pagina per pagina.
- **Messaggio di errore/conferma quando un'operazione viene rifiutata dal backend** (es.
  `licenzia_dipendente`/`disattiva_camion`/`elimina_squadra` rifiutano con `ok=False, motivo=...`
  se la risorsa è coinvolta in un viaggio non concluso): nessun componente di libreria per
  mostrarlo. In `gui/pages/dipendenti.py` per ora si usa un `QMessageBox.warning()` nativo
  (funzionale ma non uno stile Sketch) — trovato perché senza feedback il pulsante "elimina"
  sembrava non fare nulla quando il backend rifiutava silenziosamente. Se lo stesso caso si
  ripete per Camion/Squadre/Viaggi, vale la pena farne un componente riusabile invece di
  ripetere `QMessageBox` pagina per pagina.

## Lavoro deliberatamente rimandato — pagina Ordini

Decisione esplicita dell'utente: la prima passata su `OrdiniPage` copre solo lista/filtri/tabella,
senza le due feature più consistenti viste nel mockup:

- **"Registra esito consegna"** (icona matita nel mockup, artboard "Ordini — Modifica (modale)"):
  non è un editor di campi generico — è il front-end di `GestoreRendicontazione.registra_esito()`
  (selettore Esito Completato/Fallito, dropdown causale condizionale, upload prova documentale via
  `carica_prova_documentale()`). Richiede un componente Dropzone/file-attach non ancora costruito.
  Applicabile solo a ordini "In consegna" (`registra_esito` rifiuta altrimenti). Da progettare come
  feature a parte, componente per componente.
- **"Importa CSV"** (bottone header, artboard "Ordini — Importa CSV — Seleziona file/Risultato"):
  flusso a 2 passi (file-picker → riepilogo `ErroreImport(riga, messaggio)`), backend già pronto
  (`GestoreLogistica.importa_ordini`/`importa_ordini_async`) ma nessun componente file-picker né
  riepilogo-errori esiste ancora nella libreria.

Entrambi visibili nel mockup ma **disabilitati** nell'implementazione attuale (tab "Esiti" e
bottone "Importa CSV"), non rimossi — coerenza visiva con il mockup senza azioni finte.

## Gap segnalato nel mockup Sketch (non una lacuna di libreria, un buco nel file .sketch)

**Artboard "Viaggi"**: la tabella disegna un'icona matita ("Modifica") su ogni riga, ma **non
esiste alcun artboard "Viaggi — Modifica (modale)"** nel file `.sketch` (verificato elencando
tutte le pagine: solo "Viaggi" lista + "Nuova pianificazione"/wizard, nessun modale di modifica),
e nessuna RF definisce un'operazione di modifica viaggio (date/composizione/ordini). Su decisione
esplicita dell'utente, `ViaggiPage._apri_modale_modifica` apre un modale **minimale non presente
nel mockup**: solo le due date previste (partenza/arrivo), l'unico dato semplice correggibile
senza toccare composizione/ordini. Se in futuro si arriva a costruire la procedura di
pianificazione e si scopre che serve modificare altro (es. riassegnare la composizione), va
rivalutato — questo modale minimale non è una base da estendere silenziosamente, è un placeholder
dichiarato per colmare un buco del mockup.

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

**Pianificazione** (`gui/pianificazione/components/`, import `from gestionale_logistica.gui.pianificazione.components import AvvioCard, CompositionCard, PlanKpiCard, RigaOrdineComposizione, RigaOrdineSuggerito, SuggestionSection, CATEGORIA_BADGE_LABELS` — `DateFilterField` promosso a `gui/components/`, vedi `## DatePicker`, ma resta riesportato anche da qui per compatibilità):

- **`PlanKpiCard(value, label, icon_name, value_color, icon_color, parent=None)`** — card KPI "flat" della Summary Row (Automatica): icona colorata senza chip circolare (diverso da `KpiCard` Dashboard), colori valore/icona indipendenti e parametrici (vedi docstring del file per i colori misurati per card, incluso il caso ambra `#B45309` di "ORDINI NON ASSEGNATI"). `card.set_value(str)` aggiorna il valore a runtime.
- **`AvvioCard(parent=None)`** — card "Avvia composizione viaggio": `Select` senza label (placeholder "Seleziona squadra") + `DateFilterField` + bottone "Avvia composizione", messaggio di errore opzionale (`show_alert`/`hide_alert`, stesso stile di `CompositionCard`). API: `set_composizioni_disponibili(list[tuple[id, "Squadra: #N"]])`, `data_selezionata() -> date`. Segnali: `avviaRequested(str, date)`, `dataChanged(date)`. **"Squadra" invece di "Composizione"** nel testo visibile all'utente (placeholder, opzioni del menu, hint "N squadre attive disponibili...") — 2026-07-16, richiesta esplicita dell'utente: la terminologia interna resta `ComposizioneSquadra`/`composizione_id`, solo l'etichetta mostrata è cambiata, per coerenza con "Seleziona squadra" già usato altrove (es. Viaggi).
- **`CompositionCard(parent=None)`** — card "Viaggio in composizione": intestazione (squadra/camion/partenza), barre Peso/Volume (`ProgressBar` 350×7px), elenco ordini nel viaggio con badge categoria (`CATEGORIA_BADGE_LABELS`: `BordoStrada`/`InstallazioneSempliceAlPiano`/`Incasso`→"Standard" bg `#EAEAEA`/testo `#2E2E2E`, `Big`/`CertificazioneGas`→bg `#FEF3C7`/testo `#B45309` — solo "Standard"/"Big" verificati nel mockup, "Certificazione Gas" è la stessa logica applicata per coerenza), riga "Aggiungi ordine" (`Select` **senza label**, vedi `## Select`, + bottone "Aggiungi"), messaggio di rifiuto opzionale (`show_alert(motivo)`/`hide_alert()`, testo rosso `#C0392B` con prefisso `⚠`, **nessun box/bordo** — solo testo, nonostante il nome "Alert Box" nel mockup), footer Annulla + bottone primario con etichetta configurabile (`set_footer_primary_label`, default "Chiudi viaggio"). API: `set_intestazione(...)`, `set_ordini(list[RigaOrdineComposizione])`, `set_ordini_disponibili(list[tuple[id, cliente]])`, `add_extra_section(widget)` (slot per un blocco extra, inserito prima di "Aggiungi ordine"). Segnali: `aggiungiOrdineRequested(str)`, `annullaRequested()`, `chiudiViaggioRequested()`.
- **`SuggestionSection(parent=None)`** — blocco "Suggerimento automatico": bottone "Suggerisci ordini", elenco righe suggerite (testo `✓  #id  ·  cliente  ·  peso kg · volume m³  ·  categoria`, Inter 12px/500 Blu Scuro `#163A6B`, misurato — diverso dal grigio hint standard), riga di riepilogo capacità (Inter 12px/500 `#9AA1AA`). API: `set_suggerimento(list[RigaOrdineSuggerito], peso_dopo, peso_massimo, volume_dopo, volume_massimo)`, `clear()`. Segnale: `suggerisciRequested()`. Pensato per essere passato a `CompositionCard.add_extra_section()`.
- **Trappola stretch verticale** (trovata 2026-07-16 costruendo Manuale): senza uno `content_layout.addStretch(1)` finale, se la card riceve più altezza di quella richiesta dal contenuto (finestra grande), `QVBoxLayout` distribuisce lo spazio in eccesso tra le label (size policy `Preferred`, non `Fixed`) invece di lasciarle compatte in cima — sintomo: gap enormi e non uniformi tra le sezioni. Fix: `addStretch(1)` in fondo al `content_layout`. Lo stesso principio vale per qualunque container QVBoxLayout con pochi widget a size policy flessibile dentro un genitore che gli passa uno stretch factor.
- **Trappola widget "fantasma" dopo `deleteLater()`** (trovata 2026-07-16): un widget rimosso da un layout con `takeAt()` si scollega dal layout ma **non si nasconde** — resta visibile alla sua ultima geometria finché `deleteLater()` non viene effettivamente processato al giro successivo dell'event loop, producendo un frame con il vecchio widget ancora sovrapposto al nuovo in un ciclo "svuota e ripopola". Fix: chiamare `widget.hide()` subito dopo `takeAt()`, prima di `deleteLater()`.
