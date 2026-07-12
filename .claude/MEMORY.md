# Indice conoscenza di progetto

KB condivisa via git — chiunque lavori su questo repo con Claude Code (Davide o Fabio) parte da qui. Autoconclusiva: nessun file qui dentro presuppone accesso a cartelle fuori da questo repository.

- [Contesto tesi e stakes di valutazione](knowledge/tesi-e-valutazione.md) — perché ogni scelta tecnica va giustificata, gap noti lato tesi
- [Modello EA](knowledge/modello-ea.md) — versione, cosa contiene, i fix noti dall'audit (da dare per fatti)
- [Materiale del docente](knowledge/materiale-docente.md) — convenzioni obbligatorie: classi analisi/progettazione, controller «use», macchine a stati, casi d'uso, matrice di mapping
- [Stack tecnologico](knowledge/stack-tecnologico.md) — librerie scelte e perché, struttura pacchetto mappata su EA
- [Convenzioni di codice](knowledge/convenzioni-codice.md) — prefisso `flg_`, pattern segreti, backend-prima-poi-GUI, CRUDBase e i suoi limiti
- [Divergenze codice vs EA](knowledge/divergenze-ea.md) — 16 differenze intenzionali, checklist per quando si aggiorna il diagramma
- [Design motore di ottimizzazione](knowledge/design-ottimizzatore.md) — funzione obiettivo RF12/RF13, geocoding offline, clustering DBSCAN + Held-Karp implementati e mergiati (PR #11)
- RF10/RF11 (composizione manuale viaggio + validazione) implementate e mergiate (PR #12) — dettagli in `knowledge/stato-e-prossimi-passi.md`
- RF14/RF19 (scheduler interno, verifica partenza automatica, report periodico) implementate su branch `feat/scheduler-rf14-rf19`, non ancora mergiate — dettagli in `knowledge/stato-e-prossimi-passi.md` e `knowledge/divergenze-ea.md` (punti 17-18)
- [Stato e prossimi passi](knowledge/stato-e-prossimi-passi.md) — cosa è fatto, cosa manca, ordine consigliato

Handoff di sessioni precedenti: `.claude/handoff/` (in questa stessa cartella).
