import numpy as np
from sklearn.cluster import DBSCAN

from gestionale_logistica.database.models import Ordine
from gestionale_logistica.logistica.geocoding import distanza_km


def raggruppa_ordini(ordini: list[Ordine], eps_km: float = 50.0, min_samples: int = 2) -> list[list[Ordine]]:
    """Raggruppa gli ordini per vicinanza geografica con DBSCAN (matrice di distanze precalcolata).

    Ordini senza coordinate note (comune non geocodificato) non hanno una
    posizione utilizzabile per il raggruppamento: vengono trattati come
    "rumore" a priori (ciascuno un cluster a se') invece di essere passati a
    DBSCAN con una distanza fittizia, che li accosterebbe arbitrariamente ad
    altri ordini.
    """
    con_coordinate = [o for o in ordini if o.lat is not None and o.lon is not None]
    senza_coordinate = [o for o in ordini if o.lat is None or o.lon is None]

    gruppi = [[o] for o in senza_coordinate]

    if not con_coordinate:
        return gruppi

    n = len(con_coordinate)
    matrice_distanze = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = distanza_km(
                con_coordinate[i].lat, con_coordinate[i].lon, con_coordinate[j].lat, con_coordinate[j].lon
            )
            matrice_distanze[i, j] = d
            matrice_distanze[j, i] = d

    etichette = DBSCAN(eps=eps_km, min_samples=min_samples, metric="precomputed").fit_predict(
        matrice_distanze
    )

    per_etichetta: dict[int, list[Ordine]] = {}
    for ordine, etichetta in zip(con_coordinate, etichette):
        if etichetta == -1:
            gruppi.append([ordine])
        else:
            per_etichetta.setdefault(etichetta, []).append(ordine)

    gruppi.extend(per_etichetta.values())
    return gruppi
