# Modello Enterprise Architect (EA) — stato e fix noti

Il modello di dominio completo (casi d'uso, diagrammi delle classi, activity, macchine a stati, sequence, deployment) vive in un file Enterprise Architect (formato `.qea`, database SQLite) **che non fa parte di questo repository**. Solo Davide ha accesso diretto al file. Questa pagina esiste per dare comunque un contesto utile senza bisogno di aprirlo.

## Versione corrente

**v0.1.4**. Contiene: casi d'uso, 3 diagrammi delle classi, 3 activity diagram, 4 state machine, 9 sequence diagram, package/componenti/deployment, con relativa copertura dei requisiti non funzionali (RNF1-RNF5, vedi `README.md` nella root del repo).

## Audit del 3/7/2026 — problemi trovati (dare per fatti)

Un audit completo ha confrontato il modello v0.1.4 con i requisiti e col materiale del docente (vedi `materiale-docente.md`), trovando **22 problemi complessivi**, di gravità mista (da bug strutturali a refusi). Il dettaglio completo vive in un documento Word che Davide sta ancora editando — non è condiviso qui, ma le voci sotto sono **stabili e vanno considerate acquisite**, non provvisorie:

- **Fix 5 — storicizzazione Squadra.** Le associazioni dirette Dipendente↔Squadra e Camion↔Squadra nel diagramma sono ridondanti/in conflitto con `ComposizioneSquadra` (che già storicizza correttamente la composizione con date di validità). Vanno rimosse a favore della sola `ComposizioneSquadra`. **Già applicato nel codice** — vedi `divergenze-ea.md`.
- **Fix 6 — controller come dipendenze, non associazioni.** Le classi controller (`GestoreCamion`, `GestioneDipendenti`, `GestioneSquadre`, `GestoreLogistica`, `GestoreRendicontazione`, `MotoreOttimizzazione`, `VisualizzaConsegneInTransito`, `VisualizzaStoricoRisorse`) sono modellate nel diagramma con associazioni a cardinalità verso le entità — vanno invece rappresentate come dipendenze `«use»` (sono logica di business, non entità persistenti). **Già applicato nel codice** (per omissione: quelle classi semplicemente non sono tabelle) — vedi `divergenze-ea.md`.
- **Fix 7 — `Dipendente.codiceFiscale` mancante nel diagramma**, nonostante sia citato come criterio di univocità nell'activity diagram "Gestione Dipendente". **Già applicato nel codice**.
- **Fix 12** — riscritto una volta da Davide direttamente nel documento, contenuto esatto non riportato qui.
- **Fix 20** — proponeva un caso d'uso "Login" minimale per l'Admin (copre RNF5). **Superato dal codice**, che implementa un modulo di autenticazione più ricco (registrazione + conferma email via OTP + login + sessioni) — vedi `divergenze-ea.md`.
- Altri problemi noti, non ancora numerati/dettagliati qui: transizioni mancanti in alcune macchine a stati, associazioni in conflitto in punti del diagramma delle classi, **deliverable interi mancanti**: la fase "Matrice di Mapping" (requisiti↔casi d'uso, richiesta come fase separata dal docente) e gli screenshot delle "classi di analisi" (vedi `materiale-docente.md` per la distinzione classi di analisi/progettazione).

**Stato di applicazione al `.qea`**: al momento in cui questo file è stato scritto, **nessuno dei 22 fix risultava ancora applicato al diagramma** — il gruppo era in fase di sola analisi/discussione sul modello. Il codice in questo repo, invece, è già avanti su alcuni di questi punti (vedi `divergenze-ea.md` per l'elenco preciso delle differenze codice↔EA).

## Perché questo file esiste

Se stai lavorando sul codice e trovi qualcosa che sembra "non corrispondere" al diagramma delle classi che qualcuno ti ha mostrato a voce, molto probabilmente è una divergenza già nota e intenzionale — controlla prima `divergenze-ea.md` prima di modificare il codice per farlo "tornare" a un diagramma che potrebbe essere lui quello disallineato.
