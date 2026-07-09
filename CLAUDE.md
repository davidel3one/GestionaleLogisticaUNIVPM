# GestionaleLogisticaUNIVPM — contesto per Claude Code

Progetto di tesi per Ingegneria del Software (UNIVPM), lavoro di gruppo (Davide + Fabio, almeno). Sistema desktop Python 3 + PySide6 per la gestione logistica di un'azienda di consegna/installazione elettrodomestici per conto di catene retail (Unieuro/MediaWorld/Expert): pianificazione viaggi (manuale/assistita/automatica), gestione flotta (camion/dipendenti/squadre), tracciamento esiti consegna. Requisiti completi (RF1-RF19, RNF1-RNF5) nella sezione "Requisiti funzionali" del `README.md` in questa stessa cartella.

**Questo repo (`dev/`) è l'unico canale condiviso tra i membri del team.** Il modello Enterprise Architect e i documenti di tesi (requisiti, report, materiale del docente) vivono fuori da qui, sul computer di Davide — per questo la conoscenza rilevante che li riguarda è riportata per esteso nei file sotto, non come puntatore a un percorso che non esiste in questo repo.

## Prima di lavorare qui, leggi

L'indice completo è in **`.claude/MEMORY.md`** — copre: contesto tesi e stakes di valutazione, stato del modello EA e i suoi fix noti, le convenzioni obbligatorie del docente, lo stack tecnologico e perché, le convenzioni di codice (es. prefisso `flg_` per i booleani), le divergenze intenzionali tra questo codice e il diagramma EA, il design del motore di ottimizzazione, e uno stato aggiornato di cosa è fatto/cosa manca.

Sessioni precedenti (decisioni, vicoli ciechi, prossimi passi concreti) sono in **`.claude/handoff/`** — leggi la più recente prima di iniziare un lavoro non banale.

## Le due regole più importanti da subito

1. **Backend prima, GUI dopo.** Non aggiungere widget/logica GUI insieme a nuove feature di backend — `gui/main_window.py` resta vuota fino a che tutta la logica non-GUI non è completa. Dettagli in `.claude/knowledge/convenzioni-codice.md`.
2. **Il codice diverge intenzionalmente dal diagramma EA in diversi punti** — vedi `.claude/knowledge/divergenze-ea.md` prima di "correggere" qualcosa per farlo tornare a un diagramma che potresti aver visto solo a voce.

## Setup e test

```bash
uv sync
uv run pytest
```

Dettagli completi (configurazione, formato CSV di import, dati di esempio) nel `README.md` di questa cartella.
