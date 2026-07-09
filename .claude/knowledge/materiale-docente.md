# Convenzioni richieste dal docente

Il docente ha fornito un esempio completo di riferimento (progetto "stabilimento balneare", non incluso in questo repo) che mostra il formato e il livello di rigore atteso per ogni fase del workflow ufficiale: Descrizione → Requisiti → Casi d'uso → Matrice di Mapping → Package di analisi → Sequenza → Attività → Classi di progettazione → Componenti → Macchine a stati → Deployment → Mockup → Implementazione → PyUnit.

Le convenzioni sotto sono le regole precise dedotte da quell'esempio — vanno rispettate quando si lavora sul modello EA (fuori da questo repo) e tenute a mente anche scrivendo il codice, perché il codice deve restare coerente con quello che poi finisce in tesi.

## Classi di analisi vs classi di progettazione

- Le **classi di analisi** hanno **solo attributi**, mai operazioni.
- Le **classi di progettazione** sono le stesse classi con le operazioni aggiunte, con una convenzione di naming precisa: `aggiungiX()`, `getInfoX()`, `ricercaXCriterio()`, `rimuoviX()`.
- Sono due deliverable separati nella tesi — le classi di analisi vanno prodotte per prime (solo struttura dati), poi arricchite in un secondo momento con le operazioni per diventare le classi di progettazione.

## Controller e associazioni

- Le classi controller (nel nostro progetto: `Gestore*`/`MotoreOttimizzazione`/`Visualizza*`) si collegano alle entità con dipendenze **`«use»`**, **mai** con associazioni a cardinalità. Questo è esattamente il **Fix 6** del modello EA (vedi `modello-ea.md`).

## Macchine a stati

- Ogni transizione ha sempre una **guardia/evento esplicito** etichettato — mai transizioni "nude" senza condizione dichiarata.

## Casi d'uso

- Ogni caso d'uso ha una scheda formale con **Constraints** (pre/post-condizioni) e **Scenarios** (Basic Path + Alternate Path, in pseudocodice numerato).
- Esiste una fase esplicita **"Matrice di Mapping"** (requisiti ↔ casi d'uso), separata dal diagramma dei casi d'uso — è un deliverable a sé, non implicito nel diagramma.

## GUI in EA

- Esiste un package **"Viste"** con classi `QWidget` (PyQt/PySide) per la GUI, modellate **in EA come parte delle classi di progettazione** — non lasciate solo all'implementazione. Quando si arriverà a progettare la GUI (vedi `convenzioni-codice.md` per la decisione "backend prima"), le classi delle viste andranno anche modellate in EA, non solo scritte in codice.
