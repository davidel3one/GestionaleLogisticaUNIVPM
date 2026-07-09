# Contesto tesi e stakes di valutazione

Questo repository (`GestionaleLogisticaUNIVPM`) è il codice di un progetto di gruppo per il corso di **Ingegneria del Software** (UNIVPM). Il progetto è modellato in Enterprise Architect (file `.qea`, **non incluso in questo repo** — vive fuori da git sul computer di Davide, vedi `modello-ea.md` per un riassunto di cosa contiene) e implementato in Python 3 qui in `dev/`.

## Perché conta più del solito

- **Prof. Traini** richiede una struttura tesina precisa: Descrizione, Glossario, Requisiti e casi d'uso, Classi di analisi, Diagrammi di Sequenza, Diagrammi di Attività, Classi di progettazione, Diagramma E-R (opzionale), Componenti, Macchine a stati, Deployment, Mockup, Test — più link al repo GitHub (questo repo).
- **Prof. Ursino** (esaminatore) ha una policy severa: un progetto giudicato insufficiente comporta **3 mesi di attesa** prima di poter ritentare, che salgono a **6 mesi** dal secondo tentativo insufficiente.
- Conseguenza pratica: **ogni scelta tecnica va giustificabile nella tesina**, non solo tecnicamente corretta. Se una funzionalità o una scelta di design non è riconducibile a un requisito documentato (RF1-RF19, RNF1-RNF5 — vedi `README.md` nella root del repo per l'elenco completo), va segnalata esplicitamente prima di implementarla, non aggiunta silenziosamente.

## Gap noti (dal lato EA/tesi, non dal codice)

- Mancano gli screenshot delle **"classi di analisi"** richieste dal docente — le classi attualmente modellate in EA sono già "classi di progettazione" (hanno operazioni, non solo attributi). Vedi `materiale-docente.md` per la distinzione esatta.
- Manca la fase **"Matrice di Mapping"** (requisiti ↔ casi d'uso), richiesta come deliverable separato dal diagramma dei casi d'uso.

Questi due gap sono lato EA/documentazione, non toccano il codice in questo repo, ma sono aperti al momento in cui questo file è stato scritto (2026-07-09).
