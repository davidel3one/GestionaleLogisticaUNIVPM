import math
from datetime import timedelta

from gestionale_logistica.database.enums import CategoriaConsegna
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.logistica.geocoding import distanza_km, distanza_penalita_km

TEMPO_INSTALLAZIONE_MINUTI = {
    CategoriaConsegna.BORDO_STRADA: 15,
    CategoriaConsegna.INSTALLAZIONE_SEMPLICE_AL_PIANO: 30,
    CategoriaConsegna.INCASSO: 45,
    CategoriaConsegna.BIG: 60,
    CategoriaConsegna.CERTIFICAZIONE_GAS: 60,
}
VELOCITA_MEDIA_KMH = 60.0

# Soglia oltre la quale tour_esatto (Held-Karp, O(2^n * n^2)) viene abbandonato
# a favore di tour_euristico. Calibrata misurando il tempo di tour_esatto su
# coordinate casuali (media di piu' ripetizioni per n):
#   n=5   ~0.00004s   n=8  ~0.0003s   n=10 ~0.0015s
#   n=12  ~0.008s     n=15 ~0.10s     n=16 ~0.23s
#   n=17  ~0.52s      n=18 ~1.19s
# La crescita e' esponenziale come atteso (~2.2x per ogni nodo in piu'). Con
# RNF4 = 3 minuti e potenzialmente decine di cluster da processare nello stesso
# calcola_piano, n=12 (~8ms per cluster) lascia un margine ampio anche quando
# molti cluster hanno quella taglia, mentre gia' da n=16 in su il costo di un
# singolo cluster sfortunato diventerebbe percepibile sul budget totale.
SOGLIA_NODI_HELD_KARP = 12

def _distanza_coppia(ordine_a: Ordine, ordine_b: Ordine) -> float:
    if ordine_a.lat is None or ordine_a.lon is None or ordine_b.lat is None or ordine_b.lon is None:
        return distanza_penalita_km()
    return distanza_km(ordine_a.lat, ordine_a.lon, ordine_b.lat, ordine_b.lon)


def tour_esatto(ordini: list[Ordine]) -> tuple[list[Ordine], float]:
    """Cammino hamiltoniano di costo minimo che parte da ordini[0] (Held-Karp).

    Non esiste un deposito nel modello dati: il "giro" e' quindi il percorso
    piu' breve che tocca ogni tappa una volta, senza dover tornare al punto di
    partenza (a differenza del TSP classico a ciclo chiuso).
    """
    n = len(ordini)
    if n <= 1:
        return list(ordini), 0.0

    dist = [[_distanza_coppia(ordini[i], ordini[j]) for j in range(n)] for i in range(n)]

    # dp[mask][j] = costo minimo di un cammino che parte da ordini[0], visita
    # esattamente l'insieme di nodi codificato dal bitmask `mask` (bit i acceso
    # = ordini[i] gia' visitato) e termina in ordini[j]. precedente[mask][j]
    # memorizza il nodo visitato subito prima di j in quel cammino ottimo, per
    # poter ricostruire il percorso a ritroso una volta trovato il minimo finale.
    taglia = 1 << n
    dp = [[math.inf] * n for _ in range(taglia)]
    precedente = [[-1] * n for _ in range(taglia)]
    dp[1][0] = 0.0

    for mask in range(taglia):
        if not (mask & 1):
            continue
        for j in range(n):
            if not (mask & (1 << j)) or dp[mask][j] == math.inf:
                continue
            costo_corrente = dp[mask][j]
            for k in range(n):
                if mask & (1 << k):
                    continue
                nuovo_mask = mask | (1 << k)
                nuovo_costo = costo_corrente + dist[j][k]
                if nuovo_costo < dp[nuovo_mask][k]:
                    dp[nuovo_mask][k] = nuovo_costo
                    precedente[nuovo_mask][k] = j

    mask_completo = taglia - 1
    ultimo, costo_totale = min(
        ((j, dp[mask_completo][j]) for j in range(n)), key=lambda t: t[1]
    )

    # Ricostruzione del cammino a ritroso: partendo dall'ultimo nodo del
    # cammino ottimo, si legge precedente[mask][j] per sapere quale nodo lo
    # precede in quello stesso cammino, si toglie j dalla maschera (bit j
    # spento = "non ancora visitato" procedendo a ritroso) e si passa al nodo
    # precedente, finche' non si arriva al nodo iniziale (precedente == -1).
    # La lista viene quindi invertita per ottenere l'ordine di visita corretto.
    ordine_visita = []
    mask = mask_completo
    j = ultimo
    while j != -1:
        ordine_visita.append(j)
        j_precedente = precedente[mask][j]
        mask ^= 1 << j
        j = j_precedente
    ordine_visita.reverse()

    return [ordini[i] for i in ordine_visita], costo_totale


def tour_euristico(ordini: list[Ordine]) -> tuple[list[Ordine], float]:
    """Nearest-neighbor greedy: parte da ordini[0], va sempre al piu' vicino non visitato."""
    n = len(ordini)
    if n <= 1:
        return list(ordini), 0.0

    visitati = [False] * n
    visitati[0] = True
    percorso = [0]
    corrente = 0
    costo_totale = 0.0

    for _ in range(n - 1):
        migliore_j = None
        migliore_d = math.inf
        for j in range(n):
            if visitati[j]:
                continue
            d = _distanza_coppia(ordini[corrente], ordini[j])
            if d < migliore_d:
                migliore_d = d
                migliore_j = j
        visitati[migliore_j] = True
        percorso.append(migliore_j)
        costo_totale += migliore_d
        corrente = migliore_j

    return [ordini[i] for i in percorso], costo_totale


def stima_durata_viaggio(ordini: list[Ordine], usa_esatto: bool) -> timedelta:
    if not ordini:
        return timedelta()

    tempo_installazione_min = sum(TEMPO_INSTALLAZIONE_MINUTI[o.categoria_consegna] for o in ordini)
    calcola_tour = tour_esatto if usa_esatto else tour_euristico
    _, distanza_tour_km = calcola_tour(ordini)
    tempo_percorrenza_min = (distanza_tour_km / VELOCITA_MEDIA_KMH) * 60

    return timedelta(minutes=tempo_installazione_min + tempo_percorrenza_min)
