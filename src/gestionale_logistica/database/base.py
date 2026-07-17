import sqlcipher3
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool
from gestionale_logistica.config import default_database_path, load_config, get_db_encryption_key

def get_database_path() -> str:
    config = load_config()
    return config.get("database", "path", fallback=default_database_path())

def _create_encrypted_connection():
    # RNF5: apre il file SQLite via il driver SQLCipher e imposta la chiave prima di
    # qualsiasi altra query - senza PRAGMA key il file resterebbe leggibile in chiaro.
    # La chiave e' racchiusa tra apici singoli con l'escaping SQL standard (raddoppio
    # dell'apice) perche' questo driver non supporta il binding a parametro su PRAGMA key.
    # check_same_thread=False: con poolclass=QueuePool una connessione aperta in un thread
    # (es. lo scheduler APScheduler) puo' essere riassegnata a un altro thread del pool
    # (es. l'import CSV asincrono, RNF3) in momenti successivi.
    connection = sqlcipher3.connect(get_database_path(), check_same_thread=False)
    key = get_db_encryption_key().replace("'", "''")
    connection.execute(f"PRAGMA key = '{key}'")
    return connection

# URL "sqlite://" senza path fa scegliere a SQLAlchemy SingletonThreadPool per default (lo
# stesso comportamento riservato a ":memory:"), inadatto a un DB su file acceduto da piu'
# thread (scheduler + import/ottimizzazione async, RNF3): una connessione piu' vecchia puo'
# essere chiusa mentre e' ancora referenziata da un altro thread. QueuePool e' lo stesso
# poolclass che l'URL su file (sqlite:///<path>) usava prima di passare al creator custom.
engine = create_engine("sqlite://", creator=_create_encrypted_connection, poolclass=QueuePool)
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
