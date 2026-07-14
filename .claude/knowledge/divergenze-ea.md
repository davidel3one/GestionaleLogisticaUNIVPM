# Divergenze codice ↔ EA (residue)

Questo file elenca **solo** ciò che ancora diverge tra il codice in `dev/` e il modello EA. Riferimento EA corrente: **`ea/progetto v0.1.7.qea`** (14/7/2026), copia di v0.1.6 su cui è stato applicato l'ultimo giro di allineamento.

**Chiuso in v0.1.6/v0.1.7 (non più elencato):** storicizzazione Squadra, `codice_fiscale`, controller come dipendenze «use» (incluso `GestoreLogistica`), rename `Squadra.id`, M:N reale `ReportConsuntivo`↔`Ordine`, PK surrogate, `FoglioViaggio` rimossa, modulo autenticazione (`Utente`/`CodiceConferma`/`Sessione` + `GestoreAutenticazione` con 7 operazioni), prefisso `flg_` ovunque, `Ordine.destinazione`→5 campi, capacità Camion, operazioni `MotoreOttimizzazione`, RNF4→3 minuti, scikit-learn, `Viaggio.IN_COMPOSIZIONE` + `verificaIdoneitaRisorsa`/`validaOrdinePerViaggio`, naming controller RF1-RF8, `negozio_partner`, `scheduler.py`, `concorrenza.py`, consolidamento `GestoreRendicontazione`, doppia FK `ComposizioneSquadra` (scelta di design), fix `Ordine.stato_ordine`→`IN_CONSEGNA` in `verifica_partenze()`.

**Chiuso nel giro v0.1.7 (14/7/2026):**
- `GestoreLogistica.getViaggiInCorso` **rimossa da EA** — era ridondante (i viaggi in corso si prendono con `select(Viaggio).where(...)` inline; l'elenco ufficiale è già `elencaConsegneInTransito`).
- `GestoreRendicontazione.ripianificaOrdiniFalliti` **rimossa da EA** — comportamento già implicito (ordine fallito torna ripianificabile via state machine `Ordine` e ripreso da `MotoreOttimizzazione`).
- **Rename** in EA per combaciare col codice: `verificaPartenza`→`verificaPartenze`, `generaReportPeriodico`→`generaReportGiornaliero`, `caricaProveDocumentali`→`caricaProvaDocumentale`.
- `clustering.py`/`stima_durata.py` **piazzati** nel diagramma di deployment (posizione approssimata, da rifinire a mano in EA).
- **`GestoreSquadre` allineato codice↔EA.** Backend implementato in `risorse/gestore_squadre.py` (task-exec + lettura mockup Sketch, memoria `piano-squadre-backend`): `visualizza_squadre` (lista filtrata: ricerca dipendente/camion, filtro stato, ordinamento data_creazione, paginazione server-side, stato derivato Attiva/In viaggio[solo IN_CORSO]/Non attiva), `dettaglio_squadra` (composizione attiva più recente + viaggi), `elimina_squadra` (soft-delete + cascata, guard solo IN_CORSO), DTO dedicati; `crea_squadra`+`apri_composizione` invariati; 273 test verdi, review superata. In EA v0.1.7 `GestoreSquadre` ora ha **esattamente i 5 metodi del codice** (`creaSquadra`, `apriComposizione`, `visualizzaSquadre`, `dettaglioSquadra`, `eliminaSquadra`): unite le due `visualizza*` in `visualizzaSquadre`, rimosse `aggiornaSquadra` e `validaComposizioneSquadra` (validazione inglobata in `apriComposizione`), aggiunte `apriComposizione`/`dettaglioSquadra`/`eliminaSquadra`. **Codice non committato**; GUI (pagina PySide6) rimandata alla fase GUI.

## Ancora aperte

### 1. `GestoreRendicontazione.inviaReport` — manca l'invio reale del report nel codice
L'operazione è **tenuta in EA di proposito**. Il problema reale non è nel diagramma ma nel codice: `genera_report_giornaliero()` **genera e salva** solo il PDF in `report/`, ma **non esiste alcun invio effettivo** del report (né email né altro canale). Manca inoltre nel modello un dato di contatto per il negozio partner. Decisione su come/se implementare l'invio: **da valutare** (utente ci sta pensando).

### 2. Varianti async RNF3 in codice, non in EA (intenzionale)
`GestoreLogistica.importa_ordini_async` e `MotoreOttimizzazione.calcola_piano_async`: **deliberatamente non modellate** in EA (sono varianti tecniche delle operazioni sincrone già presenti; modellarle appesantirebbe il diagramma senza valore analitico).

### 3. GUI `gui/components/` non modellata (Fix 10 / package "Viste")
`Button`, `Card`, `TabBar`, `Table` (+`RowAction`), `Modal`, `form_field` (5 tipi), `Tooltip`: nessun equivalente in EA. **Deliberatamente rimandato** — è il package "Viste" da modellare quando la GUI sarà stabile.
