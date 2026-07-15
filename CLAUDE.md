# GestionaleLogisticaUNIVPM — contesto per Claude Code

Progetto di tesi per Ingegneria del Software (UNIVPM), lavoro di gruppo (Davide + Fabio, almeno). Sistema desktop Python 3 + PySide6 per la gestione logistica di un'azienda di consegna/installazione elettrodomestici per conto di catene retail (Unieuro/MediaWorld/Expert): pianificazione viaggi (manuale/assistita/automatica), gestione flotta (camion/dipendenti/squadre), tracciamento esiti consegna. Requisiti completi (RF1-RF19, RNF1-RNF5) nella sezione "Requisiti funzionali" del `README.md` in questa stessa cartella.

**Questo repo (`dev/`) è l'unico canale condiviso tra i membri del team.** Il modello Enterprise Architect e i documenti di tesi (requisiti, report, materiale del docente) vivono fuori da qui, sul computer di Davide — per questo la conoscenza rilevante che li riguarda è riportata per esteso nei file sotto, non come puntatore a un percorso che non esiste in questo repo.

## Prima di lavorare qui, leggi

L'indice completo è in **`.claude/MEMORY.md`** — copre: contesto tesi e stakes di valutazione, stato del modello EA e i suoi fix noti, le convenzioni obbligatorie del docente, lo stack tecnologico e perché, le convenzioni di codice (es. prefisso `flg_` per i booleani), le divergenze intenzionali tra questo codice e il diagramma EA, il design del motore di ottimizzazione, e uno stato aggiornato di cosa è fatto/cosa manca.

Sessioni precedenti (decisioni, vicoli ciechi, prossimi passi concreti) sono in **`.claude/handoff/`** — leggi la più recente prima di iniziare un lavoro non banale.

## Le tre regole più importanti da subito

1. **Fase GUI in corso** (il backend è completo). La GUI si costruisce in `gui/` con una libreria di componenti riusabili — vedi le **REGOLE OBBLIGATORIE GUI** qui sotto: sono vincolanti, non facoltative. (Storico: valeva "backend prima, GUI dopo"; ora il backend non-GUI è concluso e la fase GUI è avviata.)
2. **Il codice diverge intenzionalmente dal diagramma EA in diversi punti** — vedi `.claude/knowledge/divergenze-ea.md` prima di "correggere" qualcosa per farlo tornare a un diagramma che potresti aver visto solo a voce.
3. **/graphify per la ricerca aperta.** Per domande di ricerca aperte o trasversali (pattern esistenti, riferimenti incrociati tra file), controlla se esiste `graphify-out/` in questo repo o nella sua cartella padre e, se sì, interrogalo con `/graphify query "..."` invece di esplorare a mano. Se sai già dove guardare, o il grafo non esiste nel tuo ambiente, usa direttamente gli strumenti normali — non è un passaggio obbligatorio, è una scorciatoia quando disponibile. Ognuno mantiene il proprio grafo localmente: non è versionato in git.

## ⛔ REGOLE OBBLIGATORIE per lo sviluppo GUI (da rispettare SEMPRE, senza eccezioni)

Queste regole valgono per **ogni** richiesta, modifica o implementazione che tocca la GUI (`gui/`). Non sono linee guida: sono vincoli. Se una regola è in conflitto con la fretta o con una scorciatoia, vince la regola.

1. **Fedeltà assoluta al mockup Sketch.** L'unica fonte di verità per QUALSIASI dettaglio visivo (colori, spaziature, radius, font/pesi, dimensioni, icone, layout, stati) è il file `sketch/gui-design.sketch`. **Mai** dedurre, stimare a occhio o inventare un valore: se non è verificabile nel Sketch, **si chiede all'utente**, non si indovina. (Errori già commessi per aver assunto invece di misurare — non ripeterli.)

2. **Consultare Sketch via MCP a OGNI implementazione.** Prima di costruire o modificare un elemento GUI, **rivedere il mockup nel Sketch tramite l'MCP** (`get_document_info`, `get_layer_tree_summary`, `get_screenshot`, e `run_code` per estrarre i valori esatti / esportare icone). Non basta averlo visto una volta: si ri-verifica ad ogni implementazione.

3. **MCP Sketch obbligatorio e funzionante — altrimenti NON si prosegue.** All'inizio di ogni lavoro GUI, verificare che l'MCP Sketch sia collegato e risponda. Se NON è collegato/funzionante, **fermarsi e richiedere obbligatoriamente all'utente di collegarlo** prima di procedere: nessun lavoro GUI va fatto senza Sketch raggiungibile. (Nota pratica: se nella sessione l'MCP non è esposto come tool nativo `mcp__sketch__*`, è comunque un endpoint HTTP JSON-RPC su `http://localhost:31126/mcp` pilotabile via `curl` — ma va comunque verificato vivo; se non risponde, si richiede il collegamento e ci si ferma.)

4. **Usare i componenti già pronti.** Esiste una libreria in `gui/components/` (Button, Card, TabBar, Table, Modal, i form_field TextField/Select/BooleanToggle/DatePicker/MultiSelect, Tooltip, Sidebar, AppShell, PageHeader, SearchField, EmptyState, e `load_lucide_icon` per le icone). **Prima di scrivere UI nuova, usare questi.** Documentazione d'uso completa in `.claude/knowledge/componenti-gui.md` — leggerla.

5. **Riuso del codice, sempre.** Riutilizzare ciò che già esiste (componenti, costanti di stile/token, helper, icone vendorizzate in `gui/assets/icons/`). **Non reinventare né riscrivere** da zero qualcosa che c'è già; non duplicare token di colore/spaziatura (importarli, non ridefinirli).

6. **Nuovo componente → prima nella libreria, poi in uso.** Se serve un elemento non ancora esistente, **NON** scriverlo inline dentro una pagina. Prima lo si aggiunge alla libreria `gui/components/` come **componente standard, riusabile e parametrico** (seguendo il processo "Aggiungere un componente nuovo" in `componenti-gui.md`: ispezionare tutte le istanze nel Sketch → estrarre lo stile esatto → gatare le scelte deterministiche con l'utente → implementare → esportare da `__init__.py` → verificare su finestra reale → documentare), **poi** lo si usa dove serve.

7. **Coerenza per ciò che il Sketch non modella.** Se una pagina o un elemento non è presente nel mockup, **restare rigorosamente sullo stesso stile, palette di colori, UI e layout** dell'app già costruita — non distaccarsi dallo stile attuale. La palette e i token sono nel Sketch (artboard "Palette") e in `componenti-gui.md`.

**Verifica visiva:** ogni componente/pagina va verificato su **finestra reale** (script di preview nello scratchpad di sessione, lanciato con `uv run python`), non solo con i test — e non fidarsi di `grab()`/screenshot offscreen per i dettagli visivi (colori/alpha): la conferma finale la dà l'utente sulla finestra vera.

## Setup e test

```bash
uv sync
uv run pytest
```

Dettagli completi (configurazione, formato CSV di import, dati di esempio) nel `README.md` di questa cartella.
