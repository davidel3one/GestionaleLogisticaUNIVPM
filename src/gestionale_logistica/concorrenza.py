import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# max_workers=1: RNF3 richiede solo di non bloccare il thread della GUI, non parallelismo reale
# tra import CSV (RF9) e motore di ottimizzazione (RF13). Con un solo worker le operazioni si
# serializzano per costruzione, eliminando sia la race sul controllo "ID gia' esistente" di
# importa_ordini() (due import concorrenti dello stesso file non si vedrebbero a vicenda) sia la
# contesa di scrittura SQLite tra worker paralleli (OperationalError: database is locked).
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gestionale-worker")


def _logga_eccezione_non_gestita(future: "Future") -> None:
    eccezione = future.exception()
    if eccezione is not None:
        logger.error("Operazione in background fallita", exc_info=eccezione)


def esegui_in_background(operazione: Callable[[], T]) -> "Future[T]":
    """RNF3: esegue un'operazione lunga (import CSV RF9, motore di ottimizzazione RF13) su un
    thread separato per non bloccare il thread della GUI. Volutamente indipendente da PySide6
    (thread pool stdlib, non QThread): la logica applicativa resta backend puro (vedi
    convenzioni-codice.md, "backend prima, GUI dopo"); il collegamento della Future risultante
    a segnali Qt per aggiornare i widget e' compito della fase GUI, non ancora iniziata.

    Logga sempre le eccezioni non recuperate: a differenza di asyncio, concurrent.futures non
    segnala in alcun modo un'eccezione rimasta in una Future il cui .result()/.exception() non
    viene mai chiamato - senza questo callback fallirebbe in silenzio totale.
    """
    future = _executor.submit(operazione)
    future.add_done_callback(_logga_eccezione_non_gestita)
    return future


def arresta_esecutore(attendi: bool = True) -> None:
    """Da chiamare alla chiusura dell'applicazione per non lasciare thread pendenti."""
    _executor.shutdown(wait=attendi)
