import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gestionale_logistica.database import models  # noqa: F401 (registra le tabelle su Base.metadata)
from gestionale_logistica.database.base import Base


@pytest.fixture
def session_factory():
    # StaticPool + check_same_thread=False: senza queste due opzioni un ":memory:" sqlite e'
    # visibile solo al thread che l'ha creato (ogni nuova connessione da un altro thread vedrebbe
    # un database vuoto separato) - necessario per i test RNF3 che eseguono query su un worker
    # thread diverso dal thread di test.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
