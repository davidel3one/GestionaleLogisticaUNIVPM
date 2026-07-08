import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database import models  # noqa: F401 (registra le tabelle su Base.metadata)
from gestionale_logistica.database.base import Base


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
