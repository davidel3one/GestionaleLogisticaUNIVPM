# Packaging: eseguibile compilato (PyInstaller)

Build testata su macOS il 2026-07-17 (Davide). Stessa spec pensata per generare anche l'eseguibile Windows — da eseguire su una macchina Windows reale, PyInstaller non compila incrociato tra piattaforme.

## Struttura output — NON versionata in git

```
dist/
  macos/GestionaleLogistica.app
  windows/GestionaleLogistica/GestionaleLogistica.exe   (dopo build su Windows)
```

`dist/` e `build/` sono in `.gitignore` (come da sempre in questo repo) — gli artefatti compilati restano locali, non finiscono in git. Si era valutato (2026-07-17) di versionare `dist/` per avere entrambe le distribuzioni già compilate nel repo, ma si è tornati indietro nella stessa sessione: build troppo pesante per git, e il `.env` reale dentro il bundle sarebbe comunque rimasto escluso (regola `.env` globale in `.gitignore`), rendendo la distribuzione committata incompleta. Scelta finale: **si versiona solo il tooling di build** (`packaging/`), non il suo output — chi vuole l'eseguibile lo builda in locale quando serve, seguendo questo documento.

`packaging/` è tracciato: contiene lo spec e gli script di build, pronti anche se non usati regolarmente.

## File di packaging

- `packaging/entry_point.py` — script minimale che chiama `gestionale_logistica.main()` (PyInstaller ha bisogno di un entry-point `.py`, non basta il `[project.scripts]` di pyproject).
- `packaging/gestionale.spec` — spec unico, cross-platform (il blocco `BUNDLE` per il `.app` scatta solo `if sys.platform == "darwin"`). Include come `datas`: le icone SVG (`gui/assets`), il CSV di geocoding (`data/geocoding`), i binari del solver CBC di `pulp` (via `collect_data_files("pulp")` — impacchetta i binari di tutte le piattaforme, comodo perché la stessa spec gira sia su mac che su Windows), e `.env` (per il seeding a primo avvio, vedi sotto).
- `packaging/build_macos.sh` — `uv run pyinstaller packaging/gestionale.spec --distpath dist/macos --workpath build/macos`.
- `packaging/build_windows.ps1` — stesso comando, `--distpath dist/windows`. Fabio: eseguire da PowerShell su una macchina Windows con `uv` installato e il repo sincronizzato (`uv sync`).

## Decisione: dove l'app compilata salva i suoi dati

Un `.app`/`.exe` lanciato da Finder/Explorer non ha una working directory affidabile — il codice precedente risolveva `config.ini`, `.env`, `.session_token` e il path del DB come relativi alla CWD, il che avrebbe rotto silenziosamente l'app compilata (config/DB non trovati). **Scelta fatta con l'utente (Davide, 2026-07-17): cartella dati utente standard del SO**, non una cartella "portable" accanto all'eseguibile:

- macOS: `~/Library/Application Support/GestionaleLogistica/`
- Windows: `%APPDATA%/GestionaleLogistica/`

Implementato in `src/gestionale_logistica/config.py`: `_is_frozen()` (controlla `sys.frozen`, impostato da PyInstaller) decide se usare la cartella dati utente o il comportamento dev invariato (CWD-relativo, com'era prima). `default_database_path()` e `default_log_path()` espongono i fallback per `database/base.py` e `__init__.py::setup_logging`. In modalità dev (`uv run ...`) nulla cambia: stessi test, stesso comportamento di sempre.

Al primo avvio da compilato, `.env` (SMTP + `DB_ENCRYPTION_KEY`) viene copiato dalla risorsa impacchettata nella cartella dati utente (`_seed_env_file()` in `config.py`) — stesso identico `.env` di sviluppo, stesso profilo di rischio: chiunque ottenga il `.app`/`.exe` può estrarne il contenuto. Va bene per test locali/demo di tesi; **se l'app viene distribuita a terzi, ruotare prima la password SMTP** (attualmente nel repo condiviso `.env`, non in questo file).

### Chi builda ed esegue in locale: creare `.env` prima del primo avvio

Chi genera la build (`packaging/build_macos.sh` o `build_windows.ps1`) e lancia l'app compilata per la prima volta su una macchina che non ha mai eseguito l'app prima deve creare a mano `.env` nella cartella dati utente (`~/Library/Application Support/GestionaleLogistica/.env` su mac, `%APPDATA%/GestionaleLogistica/.env` su Windows), copiando `dev/.env.example` e valorizzandolo — altrimenti crash al primo avvio (`KeyError: DB_ENCRYPTION_KEY`, nessun fallback previsto di proposito). Va fatto una sola volta per macchina: una volta scritto lì, `_seed_env_file()` lo trova già presente e non lo tocca più. In modalità sviluppo (`uv run ...`) questo non c'entra: si continua a usare il `.env` nella root di `dev/`, invariato.

## Verificato funzionante (macOS, arm64)

App avviata via `open`, form di registrazione OTP renderizzato correttamente (icone SVG, font, layout), DB cifrato creato in `~/Library/Application Support/GestionaleLogistica/gestionale.db`, log scritto correttamente, scheduler APScheduler avviato e arrestato senza errori alla chiusura.
