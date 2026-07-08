from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from gestionale_logistica.config import load_config

def get_database_url() -> str:
    config = load_config()
    db_path = config.get("database", "path", fallback="gestionale.db")
    return f"sqlite:///{db_path}"

engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


@event.listens_for(engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite ignora le ForeignKey per compatibilita' storica: senza questa PRAGMA,
    # un composizione_id/foglio_viaggio_id/ordine_id/causale_id inesistente verrebbe
    # accettato silenziosamente invece di essere rifiutato con IntegrityError.
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

class Base(DeclarativeBase):
    pass
