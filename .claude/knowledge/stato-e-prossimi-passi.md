# Stato del progetto e prossimi passi

Ultimo aggiornamento: 2026-07-09. Per lo stato git aggiornato in tempo reale, `git log`/`gh pr list` restano l'unica fonte autorevole — questa pagina è un'istantanea di orientamento, non sostituisce quello.

## Fatto

- Modello dati completo (`database/models.py`, `database/enums.py`), con tutte le entità del dominio, booleani con prefisso `flg_`.
- Import ordini da CSV (RF9), con validazione header, scarto righe malformate/ID duplicati (`logistica/gestore_logistica.py`), coperto da test.
- Modulo di autenticazione Admin (RNF5): registrazione, conferma email via OTP (bcrypt, scadenza 10 min, max 5 tentativi, cooldown 60s), login, sessioni (3 ore, token). Bug corretto il 2026-07-09: `login()` ora verifica correttamente `flg_confermata` prima di autenticare.
- CRUD generico (`database/crud_base.py`) + istanze minime per `Camion`/`Dipendente`/`Squadra`/`ComposizioneSquadra` (in `risorse/`) e per `EsitoConsegna`/`CausaleFallimento`/`RegistroEsiti`/`Allegato`/`ReportConsuntivo` (in `rendicontazione/`) — vedi `convenzioni-codice.md` per i limiti (nessuna logica di business sopra il CRUD, `delete()` è hard-delete non soft-delete).
- `FoglioViaggio` rimossa (vedi `divergenze-ea.md`).
- Bootstrap applicazione: creazione schema DB, logging su file, avvio finestra principale PySide6 (ancora vuota, per scelta — vedi `convenzioni-codice.md`, "backend prima, GUI dopo").
- Suite pytest verde: 24 test.

## Non ancora fatto

- **RF1-RF8** (gestione risorse umane e mezzi): la logica di business reale sopra il CRUD generico — soft delete corretto (`update` non `delete`), validazioni, criteri di univocità, viste "risorse attive" vs "storico risorse".
- **RF10-RF14** (composizione viaggi, validazione vincoli in tempo reale, motore di ottimizzazione): vedi `design-ottimizzatore.md` per la formulazione già decisa — codice non ancora scritto, `ottimizzazione/` è ancora scheletro vuoto. Manca anche un campo di capacità (peso/volume massimo) su `Camion`, prerequisito per i vincoli.
- **RF15-RF19** (rendicontazione ed esiti): stessa situazione di RF1-8, il CRUD generico esiste ma non la logica applicativa.
- Scheduler interno (APScheduler) per i trigger automatici (RF14 verifica partenza, RF19 report delle 21:00).
- Multithreading (RNF3) — import CSV e motore di ottimizzazione devono girare in thread separati dalla GUI.
- GUI vera e propria (in blocco unico, quando tutto il backend sarà pronto).
- Geolocalizzazione (vedi `design-ottimizzatore.md`): tabella comune→coordinate, campi lat/lon su `Ordine`.
- Riportare su EA tutte le divergenze accumulate (vedi `divergenze-ea.md`) e i 22 fix dell'audit (vedi `modello-ea.md`).

## File morti / piccoli refusi da sistemare quando si torna su quella parte

- `gui/style.py` (119 righe di costanti di stile PySide6) non è importato da nessuna parte — `main_window.py` è tornato a 8 righe dopo la richiesta di rimuovere la GUI da una PR. Da tenere in attesa della GUI vera, o rimuovere — non deciso.
- `risorse/gestore_sqaudre.py` ha un refuso nel nome file (manca la "u": dovrebbe essere `gestore_squadre.py`).
- `dati_esempio/Ordini_Expert_20260706.csv` ha un header diverso da quello atteso dall'import (`RequiereSponda;RequiereCertGas` invece di `Volume`) — con il codice attuale verrebbe scartato per intero.

## Prossimi passi consigliati, in ordine

1. Aggiungere i campi di capacità mancanti su `Camion` (peso massimo, volume massimo) — sblocca RF12/RF13.
2. Procurare la tabella comune→coordinate per il geocoding offline.
3. Iniziare l'implementazione di `ottimizzazione/` seguendo `design-ottimizzatore.md`.
4. Completare la logica reale dietro il CRUD generico per RF1-8 e RF15-19.
5. Scheduler (RF14/RF19) e multithreading (RNF3).
6. Riportare le divergenze accumulate sul modello EA.
7. GUI, come blocco unico finale.
