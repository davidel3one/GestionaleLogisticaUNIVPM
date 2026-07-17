# Indice conoscenza di progetto

KB condivisa via git — chiunque lavori su questo repo con Claude Code (Davide o Fabio) parte da qui. Autoconclusiva: nessun file qui dentro presuppone accesso a cartelle fuori da questo repository.

- [Contesto tesi e stakes di valutazione](knowledge/tesi-e-valutazione.md) — perché ogni scelta tecnica va giustificata, gap noti lato tesi
- [Modello EA](knowledge/modello-ea.md) — versione, cosa contiene, i fix noti dall'audit (da dare per fatti)
- [Materiale del docente](knowledge/materiale-docente.md) — convenzioni obbligatorie: classi analisi/progettazione, controller «use», macchine a stati, casi d'uso, matrice di mapping
- [Stack tecnologico](knowledge/stack-tecnologico.md) — librerie scelte e perché, struttura pacchetto mappata su EA
- [Convenzioni di codice](knowledge/convenzioni-codice.md) — prefisso `flg_`, pattern segreti, backend-prima-poi-GUI, CRUDBase e i suoi limiti
- [Divergenze codice vs EA](knowledge/divergenze-ea.md) — 20 differenze intenzionali, checklist per quando si aggiorna il diagramma
- [Design motore di ottimizzazione](knowledge/design-ottimizzatore.md) — funzione obiettivo RF12/RF13, geocoding offline, clustering DBSCAN + Held-Karp implementati e mergiati (PR #11)
- RF10/RF11 (composizione manuale viaggio + validazione) implementate e mergiate (PR #12) — dettagli in `knowledge/stato-e-prossimi-passi.md`
- RF1-RF8 (intero range, gestione risorse umane e mezzi) mergiate in `main` (PR #15) — dettagli in `knowledge/stato-e-prossimi-passi.md` e `knowledge/divergenze-ea.md` (punto 17)
- RF14/RF19 (scheduler interno, verifica partenza automatica, report periodico) mergiate in `main` (PR #13) — dettagli in `knowledge/stato-e-prossimi-passi.md` e `knowledge/divergenze-ea.md` (punto 19)
- RF15-RF18 (registrazione esito, ripianificazione, prove documentali, consegne in transito) mergiate in `main` (PR #17), poi consolidate su un'unica `GestoreRendicontazione` (branch `feat/gestore-rendicontazione`) — nessuna divergenza EA residua sul naming dei controller, dettagli in `knowledge/stato-e-prossimi-passi.md`
- RNF3 (multithreading, nuovo `concorrenza.py`) implementato su branch `feat/multithreading-rnf3`, mergiato `main` al suo interno per risolvere i conflitti (PR #14, in attesa del merge finale) — dettagli in `knowledge/stato-e-prossimi-passi.md` e `knowledge/divergenze-ea.md` (punto 20)
- [Stato e prossimi passi](knowledge/stato-e-prossimi-passi.md) — cosa è fatto, cosa manca, ordine consigliato
- [Componenti GUI riusabili](knowledge/componenti-gui.md) — Button (5 varianti), Card (container), icone Lucide (`load_lucide_icon`), come aggiungere un nuovo componente. Libreria avviata prima del completamento del backend (override consapevole di "backend prima, GUI dopo", vedi sopra)
- [Packaging: eseguibile compilato](knowledge/packaging-build.md) — PyInstaller, spec unico mac/Windows in `packaging/`, dati app in cartella utente standard del SO (non portable), build macOS verificata 2026-07-17

Handoff di sessioni precedenti: `.claude/handoff/` (in questa stessa cartella).
