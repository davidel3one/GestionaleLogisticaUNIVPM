# Divergenze intenzionali tra il codice e il diagramma EA

Il modello dati in `database/models.py` è **più avanti** del diagramma delle classi in EA (che non fa parte di questo repo — vedi `modello-ea.md`). Le differenze sotto sono **scelte deliberate**, non bug da "correggere" per farle tornare a un diagramma che comunque non hai sotto mano — semplicemente il diagramma non è ancora stato aggiornato per rifletterle.

1. **Storicizzazione Squadra (Fix 5).** Nessuna associazione diretta Dipendente↔Squadra o Camion↔Squadra. L'unico modo per risalire a dipendenti/camion di una squadra è tramite `ComposizioneSquadra` (con `data_inizio_validita`/`data_fine_validita`). Di conseguenza `Viaggio` non ha campi `squadra`/`camion` diretti, ma un unico `composizione_id` → FK a `ComposizioneSquadra`.
2. **`Dipendente.codice_fiscale`** (unique) — presente in codice, era assente dal diagramma (Fix 7).
3. **Controller non sono tabelle (Fix 6).** `GestoreCamion`, `GestioneDipendenti`, `GestioneSquadre`, `GestoreLogistica`, `GestoreRendicontazione`, `MotoreOttimizzazione` e le classi `Visualizza*` sono logica applicativa, non entità SQLAlchemy — non hanno `__tablename__`.
4. **Naming: `Squadra.id`**, non `Squadra.codiceSquadra` — uniformità con le altre entità (`Dipendente.id`, `Camion.id`, `Ordine.id`), puro rename, non un fix di correttezza.
5. **`ComposizioneSquadra` ↔ `Dipendente`: due FK esplicite** (`dipendente_1_id`, `dipendente_2_id`, entrambe verso `dipendenti.id`), non una tabella associativa N:N — scelta di semplicità per una cardinalità fissa a 2.
6. **`ReportConsuntivo.ordini`** è una vera relazione M:N (tabella associativa `report_ordini`), non un attributo scalare come nel diagramma.
7. **PK surrogate aggiunte** dove il diagramma non ne definisce una: `EsitoConsegna`, `Allegato`, `RegistroEsiti`, `ReportConsuntivo` hanno tutte un `id` intero autoincrementante — necessità di persistenza.
8. **`FoglioViaggio` rimossa dal codice.** Il gruppo ha deciso che è ridondante — bastano `Viaggio` + `GestoreLogistica`. Rimossi la classe, l'enum `StatoFoglio`, il campo `Viaggio.foglio_viaggio_id`. I metodi che stavano su `FoglioViaggio` migrano su `GestoreLogistica`; il raggruppamento dei viaggi per giornata (es. per RF19) si fa con una query diretta su `Viaggio.data_partenza_prevista`.
9. **Modulo di autenticazione (`autenticazione/`)** — tre classi nuove (`Utente`, `CodiceConferma`, `Sessione`) e un enum `RuoloUtente`, senza equivalente nel diagramma EA. Copre (in versione più ricca) RNF5 e il Fix 20. `Utente` ha un campo `ruolo` (enum, per ora solo `ADMIN`) invece di una classe `Amministratore` dedicata, per scalabilità futura a più account/ruoli senza migrazione strutturale — il vincolo "un solo utente per ora" è enforcement applicativo (`GestoreAutenticazione.esiste_almeno_un_utente()`), non uno schema constraint.
10. **Prefisso `flg_` su tutti i booleani** (vedi `convenzioni-codice.md`) — il diagramma EA usa ancora nomi semplici (`attivo`, `certificazioneGas`, ecc.).

Nessuna di queste richiede una modifica al codice per "allinearsi" — è il contrario: quando qualcuno riprende in mano il diagramma EA, questa lista è la checklist di cosa riportare lì.
