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

## AGGIORNAMENTO 2026-07-10 — prima implementazione cancellata, redesign in corso

Una prima implementazione (`ottimizzazione/motore_ottimizzazione.py`, branch `feat/ottimizzatore-rf12-rf13`, single-MILP con termine di dispersione pesato secondo la formulazione sopra) è stata scritta e passava 48/48 test, ma la code review ha trovato un **bug bloccante**: l'EPSILON del termine di dispersione (0.001) non garantiva che fosse davvero subordinato al termine dominante — con distanze reali fino a 1400km, una singola coppia lontana può pesare più di un intero ordine servito, facendo scartare al solver ordini idonei e capienti. Inoltre, per rispettare RNF4 (30s), era stata introdotta un'euristica non approvata (limitare la dispersione ai 6 vicini geografici più prossimi per ordine) perché il solo pre-filtro peso/volume non bastava a contenere il numero di variabili ausiliarie (quasi ogni coppia di ordini passa il pre-filtro con camion realisticamente capienti).

**Discutendo il fix è emersa una proposta di redesign più ampia**: invece di un singolo MILP con penalità di dispersione, fare PRIMA un clustering geografico di tutti gli ordini candidati (punti vicini raggruppati, es. DBSCAN), POI per ogni cluster risolvere un knapsack quasi-esatto (stessa formulazione di RF12, senza bisogno del termine di dispersione — la vicinanza è già garantita dal clustering a monte), iterando sugli ordini che restano fuori dal primo viaggio di un cluster. Questo elimina alla radice il bug EPSILON e le euristiche arbitrarie sulle coppie.

**In più è stato proposto un vincolo NUOVO**: un viaggio deve rispettare un "orario di lavoro umano" (non solo peso/volume), il che richiede stimare la durata del viaggio — e quindi riapre la decisione "non è un problema di instradamento (VRP)" presa il 2026-07-09 sopra in questa pagina. Non ancora formalizzato se verrà affrontato con una stima approssimata (tempo fisso per ordine + stima di percorrenza dal cluster) o rimandato.

**Il piano precedente è stato cancellato**; la pianificazione è stata rifatta da capo con la skill `task-exec` incorporando questa nuova direzione.

## AGGIORNAMENTO 2026-07-11 — piano v2 approvato (redesign)

Formalizzato il redesign proposto sopra, con pre-mortem eseguito e ripiegato nel piano:

- **Clustering**: scikit-learn DBSCAN (nuova dipendenza, `eps`~50km/`min_samples`=2 di default, da validare su un CSV reale). Ordini "rumore" (isolati) mai scartati: prima tentativo di aggiunta a un viaggio/cluster vicino se capacità/idoneità/durata lo permettono, altrimenti viaggio dedicato.
- **Vincolo di durata**: un viaggio non supera `durata_viaggio` (stesso parametro di `applica_piano`, riusato). Durata = tempo di installazione per ordine (**per `CategoriaConsegna`**, configurabile con default: BordoStrada 15min, InstallazioneSemplice 30min, Incasso 45min, Big 60min, CertificazioneGas 60min) + tempo di percorrenza stimato (velocità media configurabile, default 40km/h).
- **Calcolo del tour**: **Held-Karp scritto a mano** (programmazione dinamica, algoritmo esatto standard per TSP su pochi nodi) — NON una libreria (esiste `python-tsp` ma scartata) e NON un MILP con eliminazione sotto-cicli (scartato: più rischio di bug silenziosi, più codice). Scelta esplicita dell'utente per poter spiegare il codice in tesi. Fallback nearest-neighbor euristico sopra una soglia di nodi da calibrare empiricamente (benchmark isolato prima di integrare, per evitare lo stesso errore di sottostima della scala che ha causato la cancellazione del piano v1).
- **RNF4 alzato da 30s a 3 minuti** (già aggiornato in `README.md` di questo repo) — il nuovo vincolo di durata rende il problema più pesante computazionalmente. Il documento dei requisiti in `docs/` (fuori da questo repo) resta da aggiornare dall'utente.
- **Non è più un ottimizzatore lineare puro end-to-end**: il knapsack (RF12 + selezione ordini per cluster in RF13) resta MILP via PuLP; il resto della pipeline RF13 (DBSCAN, Held-Karp, rimozione greedy per rientrare nella durata) sono algoritmi diversi, non programmazione lineare. Architettura ibrida, chiarita esplicitamente con l'utente.
- **IMPLEMENTATO, REVISIONATO, STRESS-TESTATO E MERGIATO IN MAIN il 2026-07-11** (PR #11 "Feat/ottimizzatore rf12 rf13", commit `7125476`; include anche i CSV di esempio nazionali in `dati_esempio/Ordini_*_Nazionale.csv`): **92/92 test verdi** (verificato indipendentemente). Code review iniziale pulita — nessun bug di correttezza, Held-Karp verificato anche a forza bruta (400 casi random). 3 finding minori risolti: guardrail del budget di tempo esteso anche al `timeLimit` del knapsack; commenti su Held-Karp per renderlo spiegabile in tesi; commento RNF4 aggiornato. Poi uno **stress test esaustivo** (26 scenari limite: input degeneri, confini `SOGLIA_NODI_HELD_KARP`, categorie non idonee, idempotenza multi-giorno, scala 150-200 ordini) — nessun bug dallo stress test stesso. Infine un **audit avversariale indipendente** (non fidarsi del "nessun bug" di chi scrive sia codice sia test) ha trovato **1 bug reale**: `calcola_piano` aveva un parametro `data` ridondante che poteva disallinearsi da `ora_partenza`, rischio di doppia prenotazione di una composizione (mai osservato in pratica, nessun chiamante reale esiste ancora, ma trap latente nell'interfaccia) — **risolto** rimuovendo `data` dalla firma, il giorno si deriva ora da `ora_partenza.date()`. Più 3 debolezze di verifica (test del guardrail tempo troppo degenere, una verifica "indipendente" in realtà circolare, un'asserzione vacua) — tutte risolte. Verifica geografica: coordinate della tabella comuni cross-controllate con fonti reali (scarti minimi), modello di durata verificato prudente (non ottimista) su percorsi reali Marche. Benchmark: 0.51s/0.08s/0.48s/0.81s a seconda dello scenario — margine enorme rispetto ai 180s disponibili.

## Punto aperto (non tecnico)

Non deciso se la geolocalizzazione vada documentata come requisito esplicito nuovo (RF20) nella tesi/EA, o trattata come dettaglio implementativo interno di RF9/RF12/RF13 — rilevante per gli stakes di valutazione (vedi `tesi-e-valutazione.md`).
