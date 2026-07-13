# Gestionale Logistica

Software desktop per la gestione logistica di un'azienda che effettua consegne e installazioni di elettrodomestici per conto di catene retail partner (es. Unieuro, MediaWorld, Expert). Progetto sviluppato per il corso di **Ingegneria del Software** (UNIVPM), modellato in Enterprise Architect e implementato in Python 3.

Il sistema copre l'intero ciclo operativo: importazione degli ordini dai negozi partner, gestione anagrafica di dipendenti e camion, composizione di squadre e viaggi (manuale, assistita o completamente automatica tramite un motore di ottimizzazione), tracciamento dello stato delle consegne e generazione di report periodici.

## Indice

- [Requisiti funzionali](#requisiti-funzionali)
- [Requisiti non funzionali](#requisiti-non-funzionali)
- [Architettura](#architettura)
- [Modello dati](#modello-dati)
- [Stato di avanzamento](#stato-di-avanzamento)
- [Struttura del progetto](#struttura-del-progetto)
- [Setup](#setup)
- [Configurazione](#configurazione)
- [Utilizzo](#utilizzo)
- [Test](#test)
- [Dati di esempio](#dati-di-esempio)

## Requisiti funzionali

### Gestione Risorse Umane e Mezzi

| ID | Requisito | Descrizione |
|----|-----------|-------------|
| RF1 | Inserisci Dipendente | Registrare un nuovo dipendente con i dati anagrafici e l'eventuale abilitazione alla certificazione gas. |
| RF2 | Modifica Dipendente | Aggiornare dati e certificazioni di un dipendente esistente, senza alterarne l'identificativo di sistema. |
| RF3 | Licenzia Dipendente | Disattivare un dipendente tramite soft delete, escludendolo dai futuri viaggi ma preservando lo storico. |
| RF4 | Inserisci Camion | Registrare un nuovo camion (targa, modello, presenza sponda idraulica). |
| RF5 | Modifica Camion | Aggiornare i dati tecnici di un camion (es. aggiunta della sponda idraulica). |
| RF6 | Disattiva Camion | Mettere un camion fuori servizio tramite soft delete, mantenendo l'integrità dei viaggi passati. |
| RF7 | Visualizza Risorse Attive | Elencare solo i dipendenti non licenziati e i camion attualmente in servizio. |
| RF8 | Visualizza Storico Risorse | Elencare tutte le risorse transitate in azienda, inclusi dipendenti licenziati e mezzi dismessi. |

### Gestione Logistica e Pianificazione

| ID | Requisito | Descrizione |
|----|-----------|-------------|
| RF9 | Importazione Ordini | Importare massivamente gli ordini dei negozi partner da file CSV/Excel. |
| RF10 | Composizione Manuale Viaggio | Creare un viaggio selezionando un set di ordini in attesa e associando una squadra e un camion idonei. |
| RF11 | Validazione Vincoli in Tempo Reale | Validazione inline durante la composizione del viaggio (es. sponda idraulica per prodotti Big, certificazione gas), che blocca le combinazioni non ammesse. |
| RF12 | Pianificazione Assistita (Suggeritore) | Da un viaggio parzialmente compilato, il motore di ottimizzazione suggerisce gli ordini rimanenti più idonei per saturare il carico (pulsante "Consiglia"). |
| RF13 | Pianificazione Automatica Massiva | Il motore di ottimizzazione genera in autonomia i viaggi della giornata, assegnando gli ordini in coda alle flotte disponibili. |
| RF14 | Verifica Partenza Automatica | Al superamento dell'orario di partenza programmato, il sistema imposta automaticamente il viaggio come "In Corso", inibendo ulteriori modifiche al carico. |

### Rendicontazione ed Esiti

| ID | Requisito | Descrizione |
|----|-----------|-------------|
| RF15 | Visualizza Consegne in Transito | Schermata riepilogativa dei soli viaggi (e relativi ordini) attualmente nello stato "In Corso". |
| RF16 | Registrazione Esito | Registrare l'esito finale di ciascun ordine di un viaggio ("Completato" o "Fallito"). |
| RF17 | Ripianificazione Ordini Falliti | Un ordine con esito "Fallito" torna automaticamente nella coda degli ordini da pianificare. |
| RF18 | Caricamento Prove da Locale | Allegare le prove documentali richieste per gli ordini falliti tramite file dialog dal file system locale. |
| RF19 | Generazione ed Invio Report Periodico | Alle 21:00, aggregazione automatica delle consegne giornaliere per negozio partner e generazione di un report consuntivo in PDF. |

## Requisiti non funzionali

| ID | Requisito | Descrizione |
|----|-----------|-------------|
| RNF1 | Stack Tecnologico e GUI | Software desktop stand-alone, core in Python 3.x, GUI con PyQt/PySide. |
| RNF2 | Persistenza e Integrità dei Dati | Database relazionale (SQLite in locale) con integrità referenziale e supporto al soft delete. |
| RNF3 | Reattività dell'Interfaccia (Non-blocking GUI) | Il motore di ottimizzazione e l'importazione massiva CSV (RF9, RF13) devono girare in thread separati per non bloccare la GUI. |
| RNF4 | Performance del Motore di Ottimizzazione | Elaborare il carico giornaliero standard (100-150 ordini) restituendo i viaggi ottimali in al massimo 3 minuti. |
| RNF5 | Conformità GDPR e Privacy | Protezione del database locale e autenticazione base dell'amministratore, a tutela dei dati anagrafici dei clienti finali. |

## Architettura

Il pacchetto `gestionale_logistica` è organizzato secondo il diagramma dei componenti del modello EA (v0.1.4), che individua tre sottosistemi applicativi più i componenti trasversali di persistenza, ottimizzazione e interfaccia:

| Componente EA | Package Python | Requisiti coperti |
|---|---|---|
| GUI | `gui/` | RNF1 |
| Database | `database/` | RNF2 |
| Motore di Ottimizzazione | `ottimizzazione/` | RF12, RF13, RNF4 |
| Gestione Risorse Umane e Mezzi | `risorse/` | RF1-RF8 |
| Gestione Logistica e Pianificazione | `logistica/` | RF9-RF14 |
| Rendicontazione ed Esiti | `rendicontazione/` | RF15-RF19 |

Il flusso applicativo previsto (RNF3) è: GUI in thread principale, importazione CSV e motore di ottimizzazione eseguiti in thread separati; uno scheduler interno (APScheduler) gestisce i trigger automatici a orario (RF14 verifica partenza, RF19 report delle 21:00).

Il modello di dominio completo (casi d'uso, diagrammi delle classi, activity, state machine, sequence, deployment) vive nel file Enterprise Architect `../ea/progetto v0.1.4.qea` (fuori da questo repository, che è scoped al solo codice). La documentazione di progetto (requisiti completi, report delle modifiche) è in `../docs/`.

## Modello dati

Entità principali (SQLAlchemy 2.0, dichiarate in `database/models.py`):

- **`Dipendente`**, **`Camion`** — anagrafiche con soft delete (`flg_attivo`), certificazione gas / sponda idraulica.
- **`Squadra`** / **`ComposizioneSquadra`** — la composizione (camion + 2 dipendenti) di una squadra è storicizzata con un intervallo di validità (`data_inizio_validita`/`data_fine_validita`); è l'unico modo per risalire ai membri di una squadra in un dato momento.
- **`Viaggio`** — collegato alla composizione squadra attiva al momento della pianificazione (non direttamente a squadra/camion), con stato (`StatoViaggio`) e gli `Ordine` assegnati.
- **`Ordine`** — richiesta di consegna/installazione da un negozio partner, con categoria (`CategoriaConsegna`: bordo strada, installazione semplice al piano, incasso, big, certificazione gas), stato (`StatoOrdine`) e negozio partner di provenienza (`negozio_partner`, opzionale, fornito esplicitamente al momento dell'importazione — usato per l'aggregazione di RF19).
- **`EsitoConsegna`** / **`RegistroEsiti`** / **`Allegato`** / **`CausaleFallimento`** — esito di ogni ordine consegnato, raggruppato per giornata in un registro, con eventuali allegati probatori in caso di fallimento.
- **`ReportConsuntivo`** — report PDF generato a fine giornata, con relazione M:N verso gli `Ordine` rendicontati.

Le divergenze intenzionali rispetto al diagramma delle classi EA v0.1.4 (in attesa di essere riportate sul modello) sono: l'associazione diretta Squadra-Dipendente/Camion è stata rimossa a favore della sola `ComposizioneSquadra` storicizzata; è stato aggiunto `Dipendente.codice_fiscale` (univoco); i controller di business (`GestoreLogistica`, motore di ottimizzazione, ecc.) non sono modellati come tabelle; l'entità `FoglioViaggio` è stata eliminata (ridondante rispetto a `Viaggio` + `GestoreLogistica`).

## Stato di avanzamento

Implementato:

- Modello dati completo (`database/models.py`, `database/enums.py`) con tutte le entità del dominio.
- Configurazione applicativa da `config.ini` (`config.py`).
- Importazione ordini da CSV (RF9), con validazione dell'header, scarto delle righe malformate e degli ID duplicati (`logistica/gestore_logistica.py`), coperta da test.
- Composizione manuale del viaggio (RF10) e validazione dei vincoli con motivo (RF11): avvio di una bozza su una `ComposizioneSquadra` idonea/attiva/libera quel giorno, aggiunta di ordini uno alla volta con validazione live di idoneità categoria↔risorsa e capacità peso/volume residua, chiusura verso lo stato definitivo `Pianificato` (`logistica/gestore_logistica.py`, nuovo stato `StatoViaggio.IN_COMPOSIZIONE`), coperta da test.
- Motore di ottimizzazione (`ottimizzazione/motore_ottimizzazione.py`): suggerimento ordini per un viaggio parzialmente compilato (RF12) e pianificazione automatica massiva della giornata (RF13, clustering geografico + knapsack di capacità + vincolo di durata del tour), coperti da test.
- Gestione risorse umane e mezzi (RF1-RF8, `risorse/`): `GestoreDipendenti` (inserisci/modifica/licenzia, RF1-RF3, univocità `codice_fiscale`) e `GestoreCamion` (inserisci/modifica/disattiva, RF4-RF6, univocità `targa`) sopra il CRUD generico, entrambi con soft delete vero (`flg_attivo`, non cancellazione fisica); `visualizza_risorse.py` con `VisualizzaRisorseAttive` (RF7) e `VisualizzaStoricoRisorse` (RF8). Un camion dismesso o un dipendente licenziato è ora escluso anche da nuovi viaggi manuali/automatici (`verifica_idoneita_risorsa()`, RF10-RF13); la dismissione stessa viene rifiutata finché la risorsa è coinvolta in un viaggio `IN_COMPOSIZIONE`/`IN_CORSO`, per evitare viaggi "zombie". Coperti da test.
- Verifica partenza automatica (RF14): `GestoreLogistica.verifica_partenze()` porta i viaggi `Pianificato` con orario di partenza superato a `InCorso` (i viaggi ancora `IN_COMPOSIZIONE` non vengono toccati), coperta da test.
- Generazione report periodico (RF19): `rendicontazione/gestore_rendicontazione.py` (`GestoreRendicontazione.genera_report_giornaliero()`) aggrega gli esiti degli ordini dei viaggi partiti in giornata per negozio partner e genera un PDF (`fpdf2`) in `report/`, persistendo `RegistroEsiti`/`ReportConsuntivo`, coperta da test. Rigenerabile per la stessa data (aggiorna la riga esistente invece di rifiutare o duplicare). L'invio del report non è implementato (nessun contatto negozio nel modello dati).
- Scheduler interno (`scheduler.py`, APScheduler): avvia i due trigger automatici a orario da `config.ini` — verifica partenza (RF14, a intervalli) e report giornaliero (RF19, a un orario fisso) — collegato al bootstrap applicativo.
- Registrazione esito, ripianificazione e prove documentali (RF15-RF18, `rendicontazione/gestore_rendicontazione.py`): `elenca_consegne_in_transito()` (RF15, viaggi `InCorso` con i relativi ordini); `registra_esito()` (RF16, causale obbligatoria se Fallito) che ri-accoda automaticamente l'ordine Fallito tra i candidati di RF12/RF13 (RF17) e `carica_prova_documentale()` (RF18, copia fisica del file in una cartella gestita, non solo il riferimento al percorso originale), coperti da test.
- Multithreading (RNF3): nuovo modulo `concorrenza.py` (`esegui_in_background()`, wrapper su `concurrent.futures.ThreadPoolExecutor`) con varianti asincrone `GestoreLogistica.importa_ordini_async()` (RF9) e `MotoreOttimizzazione.calcola_piano_async()` (RF13), coperte da test. Non basato su `QThread`: il collegamento a segnali Qt per aggiornare la GUI è compito della fase GUI, non ancora iniziata.
- Bootstrap applicazione: creazione schema DB, logging su file, avvio scheduler interno, avvio finestra principale PySide6 (`__init__.py`, `gui/main_window.py` — al momento una finestra vuota).
- Conformità GDPR e Privacy (RNF5): autenticazione amministratore con login e OTP via email (`autenticazione/`, bcrypt per l'hashing delle password), coperta da test — non ancora agganciata all'avvio dell'applicazione, rimandata alla fase GUI. Protezione del database locale via cifratura SQLCipher (`database/base.py`): il file `gestionale.db` è illeggibile senza la chiave impostata in `DB_ENCRYPTION_KEY`, coperta da test.

## Struttura del progetto

```
dev/
├── pyproject.toml              # progetto uv, dipendenze, entry point
├── config.ini                  # configurazione runtime (db, logging, scheduler)
├── dati_esempio/               # CSV di esempio per l'import ordini
├── scripts/
│   └── importa_csv.py          # CLI per l'importazione ordini da riga di comando
├── src/gestionale_logistica/
│   ├── __init__.py             # entry point: bootstrap DB, logging, scheduler, avvio GUI
│   ├── config.py                # loader di config.ini
│   ├── concorrenza.py           # esecuzione in background (RNF3) per import CSV e motore di ottimizzazione
│   ├── scheduler.py             # trigger automatici a orario (RF14, RF19) via APScheduler
│   ├── database/
│   │   ├── base.py              # engine, sessionmaker, DeclarativeBase (connessione cifrata SQLCipher, RNF5)
│   │   ├── models.py            # entità SQLAlchemy
│   │   └── enums.py             # enumerazioni di stato/categoria
│   ├── gui/
│   │   └── main_window.py       # finestra principale PySide6
│   ├── logistica/
│   │   ├── gestore_logistica.py # import ordini (RF9, con variante async RNF3), composizione/validazione viaggio (RF10/RF11), verifica partenza (RF14)
│   │   └── geocoding.py          # geocodifica offline dei comuni italiani
│   ├── ottimizzazione/          # motore di ottimizzazione: suggerimento (RF12), pianificazione automatica (RF13, con variante async RNF3)
│   ├── risorse/
│   │   ├── gestore_dipendenti.py # RF1-RF3
│   │   ├── gestore_camion.py     # RF4-RF6
│   │   └── visualizza_risorse.py # RF7-RF8
│   └── rendicontazione/
│       └── gestore_rendicontazione.py       # consegne in transito (RF15), esiti/ripianificazione/prove (RF16-RF18), report periodico (RF19)
└── tests/
    ├── conftest.py               # fixture DB in-memory
    ├── test_config.py
    ├── test_import_ordini.py
    ├── test_logistica.py         # RF10/RF11
    ├── test_gestore_logistica_rf14.py       # RF14
    ├── test_ottimizzazione.py    # RF12/RF13
    ├── test_gestore_rendicontazione_rf19.py # RF19
    ├── test_scheduler.py         # wiring APScheduler (RF14/RF19)
    ├── test_gestore_esiti.py               # RF16-RF18
    ├── test_visualizza_consegne_transito.py # RF15
    ├── test_gestore_dipendenti.py           # RF1-RF3
    ├── test_gestore_camion.py               # RF4-RF6
    ├── test_visualizza_risorse.py           # RF7-RF8
    └── test_concorrenza_rnf3.py  # RNF3
```

## Setup

Requisiti: Python 3.13+ e [uv](https://docs.astral.sh/uv/).

```bash
cd dev
uv sync
```

## Configurazione

Le impostazioni runtime sono in `config.ini`:

```ini
[database]
path = src/gestionale_logistica/data/database/gestionale.db

[logging]
level = INFO
file = app.log

[scheduler]
verifica_partenza_intervallo_minuti = 5
report_orario = 21:00
```

`gestionale.db` e `app.log` sono generati a runtime e non sono versionati (vedi `.gitignore`). Lo stesso vale per `report/`, la cartella in cui `GestoreRendicontazione.genera_report_giornaliero()` (RF19) scrive i PDF generati.

I segreti non versionati (credenziali SMTP, chiave di cifratura del database) vivono in un file `.env` locale, non tracciato da git, caricato con `python-dotenv`. Copia `.env.example` in `.env` e valorizza le variabili, tra cui `DB_ENCRYPTION_KEY` — la passphrase con cui `database/base.py` cifra il file SQLite tramite SQLCipher (RNF5). Senza questa variabile l'avvio dell'applicazione fallisce con `KeyError`.

Il progetto non ha un sistema di migrazioni: se hai gia' un `gestionale.db` locale creato prima di questo branch (es. da RF9), la prima query su `Ordine` dopo il pull fallira' con `OperationalError: no such column: ordini.negozio_partner` (colonna nuova, aggiunta per RF19). Cancella il file `gestionale.db` locale — verra' ricreato automaticamente con lo schema aggiornato al prossimo avvio. Lo stesso vale se hai un `gestionale.db` locale creato prima dell'introduzione della cifratura SQLCipher: il file preesistente non è cifrato e non è leggibile dal nuovo codice; cancellalo e verrà ricreato cifrato al prossimo avvio.

## Utilizzo

Avvio dell'applicazione (crea lo schema del database se non esiste, avvia lo scheduler interno e apre la finestra principale):

```bash
uv run gestionale-logistica
```

Importazione ordini da CSV da riga di comando (RF9):

```bash
uv run python scripts/importa_csv.py dati_esempio/Ordini_Unieuro_20260706.csv Unieuro
```

Il file CSV deve avere separatore `;` e le colonne, in ordine: `ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia`. La categoria deve corrispondere a uno dei valori di `CategoriaConsegna` (`BordoStrada`, `InstallazioneSempliceAlPiano`, `Incasso`, `Big`, `CertificazioneGas`). La `Provincia` è la sigla (es. `AN`, `MC`, `PU`) della città di destinazione; viene persistita e usata per la geocodifica offline del comune. Righe con ID già presente a database o con campi numerici non validi vengono scartate e riportate come errori, senza interrompere l'importazione delle righe valide; un header non riconosciuto rifiuta invece l'intero file.

## Test

```bash
uv run pytest
```

## Dati di esempio

`dati_esempio/` contiene tre file CSV di ordini generati per i negozi partner Unieuro, MediaWorld ed Expert (formato descritto sopra), usati sia per test manuali dell'importazione sia come fixture nella suite di test automatici.
