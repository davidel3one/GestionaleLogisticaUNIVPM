from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gestionale-worker")


def esegui_in_background(operazione: Callable[[], T]) -> "Future[T]":
    """RNF3: esegue un'operazione lunga (import CSV RF9, motore di ottimizzazione RF13) su un
    thread separato per non bloccare il thread della GUI. Volutamente indipendente da PySide6
    (thread pool stdlib, non QThread): la logica applicativa resta backend puro (vedi
    convenzioni-codice.md, "backend prima, GUI dopo"); il collegamento della Future risultante
    a segnali Qt per aggiornare i widget e' compito della fase GUI, non ancora iniziata.
    """
    return _executor.submit(operazione)


def arresta_esecutore(attendi: bool = True) -> None:
    """Da chiamare alla chiusura dell'applicazione per non lasciare thread pendenti."""
    _executor.shutdown(wait=attendi)
