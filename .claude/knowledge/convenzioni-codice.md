# Convenzioni di codice del progetto

## Booleani: prefisso `flg_`

Deciso il 2026-07-09: **tutti** gli attributi booleani del modello dati (`database/models.py`) usano il prefisso `flg_` — es. `Dipendente.flg_attivo`, `Dipendente.flg_certificazione_gas`, `Camion.flg_sponda_idraulica`, `Camion.flg_attivo`, `Squadra.flg_attiva`, `ComposizioneSquadra.flg_attiva`, `Utente.flg_confermata`. Scelta esplicita e consapevole (non uno stile "storico" da cui deviare per errore) — usarlo per qualunque nuovo campo booleano si aggiunga.

## Pattern segreti

- `config.ini` resta **tracciato su git**, e **non deve mai contenere segreti reali** — era già pubblico prima che servissero credenziali vere.
- Le credenziali SMTP (invio codice OTP via Gmail SMTP + App Password, usate dal modulo di autenticazione) vivono in un `.env` **non tracciato**.
- `.env.example` (con placeholder, non valori reali) è tracciato come documentazione del formato atteso.

## Ordine di sviluppo: backend prima, GUI dopo

Decisione di team: si completa **tutta la logica non-GUI** (parsing, persistenza, pianificazione, ottimizzazione, rendicontazione) prima di lavorare sulla GUI, che verrà affrontata **in blocco unico** più avanti, non modulo per modulo insieme a ogni feature di backend. `gui/main_window.py` resta intenzionalmente una `QMainWindow` vuota fino a quel momento — non aggiungere widget/logica GUI insieme a nuove feature di backend senza discuterne prima.

## Accesso ai dati: query dirette, non un livello di astrazione custom

I moduli applicativi (es. `logistica/gestore_logistica.py`) interrogano `database/models.py` **direttamente** via SQLAlchemy (`select(...)`, `session.scalars(...)`) — non c'è (e non serve inventare) un ulteriore livello di repository/DAO sopra i modelli. Nuovi moduli (es. il motore di ottimizzazione) dovrebbero seguire lo stesso pattern.

## `database/crud_base.py` — CRUD generico

Arrivato con la PR "CRUD operations": una classe generica `CRUDBase[ModelType]` con `get`, `get_all`, `create`, `update`, `delete`, usata per istanziare CRUD minimi per `Camion`, `Dipendente`, `Squadra`/`ComposizioneSquadra` (in `risorse/`) e per `EsitoConsegna`/`CausaleFallimento`/`RegistroEsiti`/`Allegato`/`ReportConsuntivo` (in `rendicontazione/gestore_rendicontazione.py`).

**Attenzione**: `CRUDBase.delete()` esegue una **DELETE fisica** (`db.delete(obj)`). I requisiti RF3 ("Licenzia Dipendente") e RF6 ("Disattiva Camion") richiedono invece un **soft delete** (il record resta, si marca `flg_attivo = False`) — per quelle operazioni va usato `update(obj_in={"flg_attivo": False})`, non `delete()`. Le istanze CRUD attuali in `risorse/` sono solo lo scheletro generico (4-5 righe ciascuna): nessuna logica di business (soft-delete corretto, validazioni, criteri di univocità come `codice_fiscale`/`targa`) è ancora implementata sopra di esse.
