# Design del motore di ottimizzazione (RF12/RF13)

Decisioni prese il 2026-07-09, **prima ancora di scrivere codice** in `ottimizzazione/` (oggi ancora scheletro vuoto — solo `__init__.py`). Non dipende dal CRUD di `risorse/`: l'ottimizzatore può interrogare `database/models.py` direttamente via SQLAlchemy, stesso pattern di `logistica/gestore_logistica.py` (vedi `convenzioni-codice.md`).

## Non è un problema di instradamento (VRP)

I requisiti non prevedono sequenziamento delle tappe o minimizzazione dei km tra indirizzi — solo raggruppamento di ordini in viaggi rispettando capacità e idoneità. È un problema di **assegnazione/knapsack**, molto più leggero di un VRP: il solver MILP scelto (PuLP + CBC) basta tranquillamente per la scala richiesta da RNF4 (100-150 ordini, risposta entro 30s).

## Funzione obiettivo RF12 (Suggeritore, viaggio parzialmente compilato)

Massimizzare il **numero di ordini aggiunti** al viaggio (non peso/volume totale, per non dover pesare arbitrariamente unità diverse), tra gli ordini idonei in coda, con vincoli rigidi:
- peso totale ≤ capacità peso residua del camion,
- volume totale ≤ capacità volume residua del camion,
- idoneità categoria↔risorsa (RF11): ordini `Big` richiedono `Camion.flg_sponda_idraulica`, ordini `CertificazioneGas` richiedono almeno un dipendente della squadra con `flg_certificazione_gas`.

È strutturalmente un knapsack 0/1.

## Funzione obiettivo RF13 (Pianificazione Automatica)

Gerarchia a due livelli, da implementare come **weighted sum in un'unica solve PuLP** (non due solve lessicografiche separate — più semplice, stesso risultato garantito scalando bene i pesi):
1. **Termine dominante**: massimizzare il numero di ordini assegnati a un viaggio nella giornata (priorità: far partire più ordini possibile).
2. **Termine subordinato** (peso ~1000x più piccolo): minimizzare la dispersione geografica degli ordini dentro ogni viaggio, usando le coordinate geocodificate (vedi sotto). Il peso ridotto garantisce che la vicinanza non faccia mai perdere un ordine assegnabile — conta solo a parità di ordini serviti.

**Escluso per ora**: rispettare eventuali date di consegna/scadenze. `Ordine.data_consegna` in `models.py` è la data di consegna **effettiva** (quando l'ordine viene chiuso), non una scadenza richiesta dal cliente/negozio — non esiste un campo per questo, e nessun requisito documentato (RF1-RF19) lo prevede. Se emerge un caso d'uso concreto, va prima aggiunto un campo dati (e probabilmente un nuovo requisito), non inventato come vincolo implicito.

## Geolocalizzazione — geocoding offline

Per il termine di dispersione geografica di RF13 servono le coordinate di ogni ordine. Decisione: **geocoding offline**, tabella locale comune→centroide (non un servizio online tipo Nominatim) — per coerenza con RNF1 ("software desktop stand-alone") e per evitare una dipendenza di rete/rate-limit durante l'import CSV (RF9).

**Scoperta utile controllando i CSV reali** in `dati_esempio/*.csv`: il campo `Indirizzo` ha sempre formato `"<via e civico>, <comune>"` — il comune è l'ultimo token dopo la virgola, pulito, **senza CAP nel testo**. Questo semplifica il geocoding: si può fare match diretto per nome comune contro una tabella comune→centroide, senza dover parsare/estrarre un CAP da un indirizzo libero.

**RISOLTO il 2026-07-10 (PR #9):** tabella `data/geocoding/comuni_coordinate.csv` (7897 comuni italiani) procurata e imbustata; `Ordine.destinazione` sostituito da `indirizzo`/`comune`/`provincia`/`lat`/`lon`; nuovo modulo `logistica/geocoding.py`; `GestoreLogistica.importa_ordini()` popola le coordinate durante l'import, con test per indirizzi malformati e comuni sconosciuti.

**Ancora da fare** (non implementato):
- Aggiungere un campo di capacità mancante su `Camion` (peso massimo, volume massimo — non esiste nel modello dati attuale, unico prerequisito rimasto per i vincoli RF12/RF13 di base, indipendentemente dal geocoding, ora risolto).
- Integrare la dispersione geografica nella funzione obiettivo di RF13 come termine subordinato pesato (non come pre-filtro/clustering separato — quella era un'ipotesi iniziale, superata dalla formulazione a weighted-sum sopra). Le coordinate sono ora disponibili su `Ordine.lat`/`Ordine.lon`.

**Nota a margine, trovata controllando gli stessi CSV, non collegata al geocoding**: `dati_esempio/Ordini_Expert_20260706.csv` ha colonne diverse (`RequiereSponda;RequiereCertGas` al posto di `Volume`) rispetto all'header atteso da `GestoreLogistica.importa_ordini()` (`COLONNE_ATTESE`) — con il codice attuale quel file verrebbe scartato per intero ("header non riconosciuto"). Non affrontato.

## Punto aperto (non tecnico)

Non deciso se la geolocalizzazione vada documentata come requisito esplicito nuovo (RF20) nella tesi/EA, o trattata come dettaglio implementativo interno di RF9/RF12/RF13 — rilevante per gli stakes di valutazione (vedi `tesi-e-valutazione.md`).
