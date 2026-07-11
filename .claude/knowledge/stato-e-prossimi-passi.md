# Stato del progetto e prossimi passi

Ultimo aggiornamento: 2026-07-11. Per lo stato git aggiornato in tempo reale, `git log`/`gh pr list` restano l'unica fonte autorevole — questa pagina è un'istantanea di orientamento, non sostituisce quello.

## Fatto

- Modello dati completo (`database/models.py`, `database/enums.py`), con tutte le entità del dominio, booleani con prefisso `flg_`.
- Import ordini da CSV (RF9), con validazione header, scarto righe malformate/ID duplicati (`logistica/gestore_logistica.py`), coperto da test.
- Modulo di autenticazione Admin (RNF5): registrazione, conferma email via OTP (bcrypt, scadenza 10 min, max 5 tentativi, cooldown 60s), login, sessioni (3 ore, token).
- CRUD generico (`database/crud_base.py`) + istanze minime per `Camion`/`Dipendente`/`Squadra`/`ComposizioneSquadra` (in `risorse/`) e per `EsitoConsegna`/`CausaleFallimento`/`RegistroEsiti`/`Allegato`/`ReportConsuntivo` (in `rendicontazione/`) — vedi `convenzioni-codice.md` per i limiti (nessuna logica di business sopra il CRUD, `delete()` è hard-delete non soft-delete).
- `FoglioViaggio` rimossa (vedi `divergenze-ea.md`).
- Bootstrap applicazione: creazione schema DB, logging su file, avvio finestra principale PySide6 (ancora vuota, per scelta — vedi `convenzioni-codice.md`, "backend prima, GUI dopo").
- **Geocoding offline (PR #9, mergiata il 2026-07-10):** `Ordine.destinazione` sostituito da `indirizzo`/`comune`/`provincia`/`lat`/`lon`; nuovo modulo `logistica/geocoding.py` + tabella statica `data/geocoding/comuni_coordinate.csv` (7897 comuni italiani). `GestoreLogistica.importa_ordini()` popola le coordinate durante l'import, con test per indirizzi malformati/comuni sconosciuti.
- **`Camion.peso_massimo`/`volume_massimo` (PR #10, mergiata il 2026-07-10):** capacità di peso/volume, prerequisito per i vincoli RF12/RF13.
- **RF12/RF13 (motore di ottimizzazione), PR #11 "Feat/ottimizzatore rf12 rf13", mergiata il 2026-07-11 (commit `7125476`):** `ottimizzazione/motore_ottimizzazione.py` con `suggerisci_ordini()` (RF12, knapsack 0/1 via PuLP/CBC) e `calcola_piano()`/`applica_piano()` (RF13, architettura a due fasi). RF13 usa clustering geografico (`ottimizzazione/clustering.py`, scikit-learn DBSCAN) → knapsack per cluster → vincolo di durata/orario di lavoro calcolato con un tour Held-Karp scritto a mano sotto una soglia di nodi calibrata empiricamente, fallback euristico nearest-neighbor sopra (`ottimizzazione/stima_durata.py`). RNF4 alzato da 30s a 3 minuti in questo passaggio. Storia completa (redesign da v1 cancellata per bug di calibrazione, stress test su 26 scenari, audit avversariale con 1 bug reale trovato e risolto) in `design-ottimizzatore.md`. Include anche 3 nuovi CSV di esempio con ordini sparsi su tutta Italia (`dati_esempio/Ordini_*_Nazionale.csv`), oltre ai 3 originali (solo Marche).
- PR #5 (caricamento duplicato/rotto via web UI) chiusa senza merge.
- Suite pytest verde: 92 test.

## Non ancora fatto

- **RF1-RF8** (gestione risorse umane e mezzi): la logica di business reale sopra il CRUD generico — soft delete corretto (`update` non `delete`), validazioni, criteri di univocità, viste "risorse attive" vs "storico risorse".
- **RF10/RF11** (composizione manuale viaggio, validazione realtime in GUI): l'idoneità categoria↔risorsa esiste già dentro l'ottimizzatore (`_ordine_idoneo`) ma non è ancora richiamabile da un flusso manuale.
- **RF15-RF19** (rendicontazione ed esiti): stessa situazione di RF1-8, il CRUD generico esiste ma non la logica applicativa.
- Scheduler interno (APScheduler) per i trigger automatici (RF14 verifica partenza, RF19 report delle 21:00).
- Multithreading (RNF3) — import CSV e motore di ottimizzazione devono girare in thread separati dalla GUI.
- GUI vera e propria (in blocco unico, quando tutto il backend sarà pronto).
- Riportare su EA tutte le divergenze accumulate (vedi `divergenze-ea.md`, 15 voci) e i 22 fix dell'audit (vedi `modello-ea.md`) — incluso il nuovo package `ottimizzazione/` (DBSCAN + Held-Karp) e il vincolo di durata che riapre la nota "non è un problema di instradamento (VRP)".
- Aggiornare il documento requisiti di tesi con RNF4 a 3 minuti (fuori da questo repo, a carico dell'utente).

## File morti / piccoli refusi da sistemare quando si torna su quella parte

- `gui/style.py` (119 righe di costanti di stile PySide6) non è importato da nessuna parte — `main_window.py` è tornato a 8 righe dopo la richiesta di rimuovere la GUI da una PR. Da tenere in attesa della GUI vera, o rimuovere — non deciso.
- `risorse/gestore_sqaudre.py` ha un refuso nel nome file (manca la "u": dovrebbe essere `gestore_squadre.py`).
- `dati_esempio/Ordini_Expert_20260706.csv` ha un header diverso da quello atteso dall'import (`RequiereSponda;RequiereCertGas` invece di `Volume`) — con il codice attuale verrebbe scartato per intero. Il nuovo `Ordini_Expert_Nazionale.csv` (PR #11) usa invece l'header corretto.

## Prossimi passi consigliati, in ordine

1. **RF10/RF11**: esporre `_ordine_idoneo()` come flusso di composizione manuale del viaggio (già pronto dentro l'ottimizzatore, manca solo il richiamo da un percorso non automatico).
2. Completare la logica reale dietro il CRUD generico per RF1-8 e RF15-19 (soft delete, validazioni, viste).
3. Scheduler (RF14/RF19) e multithreading (RNF3).
4. Riportare le divergenze accumulate (15 voci) sul modello EA, incluso il package `ottimizzazione/` e la nota "non è un VRP" da aggiornare.
5. GUI, come blocco unico finale.
