# Stack tecnologico e perché

Scelto il 2026-07-05 con l'intero gruppo, scaffolding iniziale fatto lo stesso giorno (progetto `uv`, package `gestionale_logistica`).

## Librerie scelte e perché (decisioni vincolanti, non ridiscutere senza un motivo forte)

- **PySide6** per la GUI — RNF1 lasciava aperto PyQt/PySide, scelto PySide6 per licenza **LGPL**, adatta a un repo pubblico di tesi senza i vincoli GPL di PyQt.
- **PuLP** (MILP, con il solver **CBC** incluso) per il Motore di Ottimizzazione (RF12/RF13) — preferito a **OR-Tools** (troppo pesante/difficile da giustificare in una tesi) e a **`scipy.optimize.milp`** (supporto MILP troppo recente/immaturo per vincoli di business complessi come i nostri). Vedi `design-ottimizzatore.md` per la formulazione del problema.
- **uv** come tool di packaging/dipendenze (scelto perché già installato sul sistema di Davide; niente Poetry).
- **APScheduler** — per i trigger a orario del deployment (RF14 verifica partenza, RF19 report delle 21:00).
- **pandas + openpyxl** — import CSV/Excel (RF9).
- **fpdf2** — generazione report PDF (RF19).
- **pytest** — suite di test.
- **bcrypt** — hashing password per il modulo di autenticazione (RNF5).
- **python-dotenv** — caricamento credenziali SMTP da `.env` (vedi `convenzioni-codice.md` per il pattern segreti).

## Struttura del pacchetto

`src/gestionale_logistica/`, mappata 1:1 sui componenti del diagramma dei componenti EA (v0.1.4):

| Componente EA | Package Python | Requisiti coperti |
|---|---|---|
| GUI | `gui/` | RNF1 |
| Database | `database/` | RNF2 |
| Motore di Ottimizzazione | `ottimizzazione/` | RF12, RF13, RNF4 |
| Gestione Risorse Umane e Mezzi | `risorse/` | RF1-RF8 |
| Gestione Logistica e Pianificazione | `logistica/` | RF9-RF14 |
| Rendicontazione ed Esiti | `rendicontazione/` | RF15-RF19 |

Flusso applicativo previsto (RNF3): GUI in thread principale, import CSV e motore di ottimizzazione eseguiti in thread separati per non bloccare l'interfaccia; uno scheduler interno (APScheduler) gestisce i trigger automatici a orario.

## Punto aperto, non risolto

Il diagramma di deployment (lato EA) nomina l'artefatto eseguibile `GestionaleLogistica.py` (file singolo), mentre lo scaffolding reale usa un layout `src/` standard con entry point via `pyproject.toml` (script `gestionale-logistica`). Sono equivalenti funzionalmente ma non letteralmente coerenti — da decidere se aggiungere una nota nel diagramma di deployment o lasciare così.
