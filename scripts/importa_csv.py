import sys
from pathlib import Path

from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python scripts/importa_csv.py <percorso_file_csv> <negozio_partner>")
        sys.exit(1)

    percorso_file = Path(sys.argv[1])
    risultato = GestoreLogistica().importa_ordini(percorso_file, sys.argv[2])

    print(f"Ordini creati: {risultato.ordini_creati}")
    if risultato.errori:
        print(f"Errori ({len(risultato.errori)}):")
        for errore in risultato.errori:
            print(f"  riga {errore.riga}: {errore.messaggio}")


if __name__ == "__main__":
    main()
