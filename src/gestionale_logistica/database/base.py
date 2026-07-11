from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from gestionale_logistica.config import load_config

def get_database_url() -> str:
    config = load_config()
    db_path = config.get("database", "path", fallback="gestionale.db")
    return f"sqlite:///{db_path}"

engine = create_engine(
    get_database_url(),
    # RNF3: importa_ordini_async/calcola_piano_async (concorrenza.py) aprono una Session su un
    # worker thread diverso dal thread che ha creato l'engine. QueuePool puo' restituire a quel
    # worker una connessione fisica creata in precedenza da un altro thread (mai usata da due
    # thread contemporaneamente, solo in momenti diversi tramite checkout/checkin del pool) - senza
    # check_same_thread=False, pysqlite la rifiuterebbe con "SQLite objects created in a thread can
    # only be used in that same thread". Sicuro perche' ogni Session resta comunque confinata a un
    # solo thread per tutta la propria durata (mai passata tra thread a meta' vita).
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)


@event.listens_for(engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite accetta la sintassi ForeignKey(...) nei modelli ma non la applica di default:
    # senza questa PRAGMA, un composizione_id/ordine_id/causale_id inesistente verrebbe
    # accettato silenziosamente invece di essere rifiutato con IntegrityError. Va ripetuta
    # ad ogni nuova connessione perche' e' un'impostazione per-connessione, non per-file.
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

class Base(DeclarativeBase):
    pass
