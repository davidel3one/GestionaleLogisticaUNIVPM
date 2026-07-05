from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from gestionale_logistica.config import load_config

def get_database_url() -> str:
    config = load_config()
    db_path = config.get("database", "path", fallback="gestionale.db")
    return f"sqlite:///{db_path}"

engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass
