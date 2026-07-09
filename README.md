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
| RNF4 | Performance del Motore di Ottimizzazione | Elaborare il carico giornaliero standard (100-150 ordini) restituendo i viaggi ottimali in al massimo 30 secondi. |
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
- **`Ordine`** — richiesta di consegna/installazione da un negozio partner, con categoria (`CategoriaConsegna`: bordo strada, installazione semplice al piano, incasso, big, certificazione gas) e stato (`StatoOrdine`).
- **`EsitoConsegna`** / **`RegistroEsiti`** / **`Allegato`** / **`CausaleFallimento`** — esito di ogni ordine consegnato, raggruppato per giornata in un registro, con eventuali allegati probatori in caso di fallimento.
- **`ReportConsuntivo`** — report PDF generato a fine giornata, con relazione M:N verso gli `Ordine` rendicontati.

Le divergenze intenzionali rispetto al diagramma delle classi EA v0.1.4 (in attesa di essere riportate sul modello) sono: l'associazione diretta Squadra-Dipendente/Camion è stata rimossa a favore della sola `ComposizioneSquadra` storicizzata; è stato aggiunto `Dipendente.codice_fiscale` (univoco); i controller di business (`GestoreLogistica`, motore di ottimizzazione, ecc.) non sono modellati come tabelle; l'entità `FoglioViaggio` è stata eliminata (ridondante rispetto a `Viaggio` + `GestoreLogistica`).

## Stato di avanzamento

Implementato:

- Modello dati completo (`database/models.py`, `database/enums.py`) con tutte le entità del dominio.
- Configurazione applicativa da `config.ini` (`config.py`).
- Importazione ordini da CSV (RF9), con validazione dell'header, scarto delle righe malformate e degli ID duplicati (`logistica/gestore_logistica.py`), coperta da test.
- Bootstrap applicazione: creazione schema DB, logging su file, avvio finestra principale PySide6 (`__init__.py`, `gui/main_window.py` — al momento una finestra vuota).

Non ancora implementato: RF1-RF8 (gestione risorse umane e mezzi), RF10-RF14 (composizione viaggi, validazione vincoli, motore di ottimizzazione), RF15-RF19 (rendicontazione, esiti, report), lo scheduler interno (RF14/RF19), il multithreading richiesto da RNF3 e l'autenticazione richiesta da RNF5. I package `ottimizzazione/`, `risorse/`, `rendicontazione/` esistono come scheletro (solo `__init__.py`).

## Struttura del progetto

```
dev/
├── pyproject.toml              # progetto uv, dipendenze, entry point
├── config.ini                  # configurazione runtime (db, logging, scheduler)
├── dati_esempio/               # CSV di esempio per l'import ordini
├── scripts/
│   └── importa_csv.py          # CLI per l'importazione ordini da riga di comando
├── src/gestionale_logistica/
│   ├── __init__.py             # entry point: bootstrap DB, logging, avvio GUI
│   ├── config.py                # loader di config.ini
│   ├── database/
│   │   ├── base.py              # engine, sessionmaker, DeclarativeBase
│   │   ├── models.py            # entità SQLAlchemy
│   │   └── enums.py             # enumerazioni di stato/categoria
│   ├── gui/
│   │   └── main_window.py       # finestra principale PySide6
│   ├── logistica/
│   │   └── gestore_logistica.py # import ordini, pianificazione (RF9-RF14)
│   ├── ottimizzazione/          # motore di ottimizzazione (RF12/RF13) - da implementare
│   ├── risorse/                 # gestione dipendenti/camion (RF1-RF8) - da implementare
│   └── rendicontazione/         # esiti e report (RF15-RF19) - da implementare
└── tests/
    ├── conftest.py               # fixture DB in-memory
    ├── test_config.py
    └── test_import_ordini.py
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

`gestionale.db` e `app.log` sono generati a runtime e non sono versionati (vedi `.gitignore`).

## Utilizzo

Avvio dell'applicazione (crea lo schema del database se non esiste e apre la finestra principale):

```bash
uv run gestionale-logistica
```

Importazione ordini da CSV da riga di comando (RF9):

```bash
uv run python scripts/importa_csv.py dati_esempio/Ordini_Unieuro_20260706.csv
```

Il file CSV deve avere separatore `;` e le colonne, in ordine: `ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia`. La categoria deve corrispondere a uno dei valori di `CategoriaConsegna` (`BordoStrada`, `InstallazioneSempliceAlPiano`, `Incasso`, `Big`, `CertificazioneGas`). La `Provincia` è la sigla (es. `AN`, `MC`, `PU`) della città di destinazione; viene persistita e usata per la geocodifica offline del comune. Righe con ID già presente a database o con campi numerici non validi vengono scartate e riportate come errori, senza interrompere l'importazione delle righe valide; un header non riconosciuto rifiuta invece l'intero file.

## Test

```bash
uv run pytest
```

## Dati di esempio

`dati_esempio/` contiene tre file CSV di ordini generati per i negozi partner Unieuro, MediaWorld ed Expert (formato descritto sopra), usati sia per test manuali dell'importazione sia come fixture nella suite di test automatici.
