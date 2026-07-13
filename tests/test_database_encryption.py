import concurrent.futures
import sqlite3
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from gestionale_logistica.database import base as database_base
from gestionale_logistica.database import models  # noqa: F401 (registra le tabelle su Base.metadata)
from gestionale_logistica.database.base import Base
from gestionale_logistica.database.models import Dipendente


@pytest.fixture
def encrypted_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "cifrato.db"
    monkeypatch.setattr(database_base, "get_database_path", lambda: str(db_path))
    monkeypatch.setattr(database_base, "get_db_encryption_key", lambda: "chiave-di-test")

    # poolclass=QueuePool replica esattamente la costruzione di database/base.py: e' quello
    # che rende deterministico il test di concorrenza qui sotto (vedi il suo commento).
    engine = create_engine(
        "sqlite://", creator=database_base._create_encrypted_connection, poolclass=QueuePool
    )
    Base.metadata.create_all(engine)
    return engine, db_path


def test_db_file_non_e_leggibile_con_sqlite_non_cifrato(encrypted_engine):
    _, db_path = encrypted_engine

    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(str(db_path)).execute("SELECT * FROM sqlite_master").fetchall()


def test_crud_funziona_con_la_chiave_corretta(encrypted_engine):
    engine, _ = encrypted_engine
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        session.add(
            Dipendente(
                id="dip-1",
                nome="Mario",
                cognome="Rossi",
                codice_fiscale="RSSMRA80A01A271Z",
                data_assunzione=datetime(2026, 1, 1),
                data_licenziamento=None,
                flg_attivo=True,
                flg_certificazione_gas=False,
            )
        )
        session.commit()

    with session_factory() as session:
        dipendente = session.get(Dipendente, "dip-1")
        assert dipendente is not None
        assert dipendente.cognome == "Rossi"


def test_engine_cifrato_regge_query_concorrenti_da_piu_thread(encrypted_engine):
    # Regressione: create_engine("sqlite://", creator=...) senza poolclass esplicito fa
    # scegliere a SQLAlchemy SingletonThreadPool (il default riservato a ":memory:"), che con
    # un DB su file acceduto da piu' thread (scheduler APScheduler + import/ottimizzazione
    # async, RNF3) chiude connessioni ancora referenziate da un altro thread, causando
    # ProgrammingError da sqlite3/sqlcipher3 su query successive. database/base.py forza
    # poolclass=QueuePool proprio per evitarlo; qui si esercita con piu' thread di quanti ne
    # reggerebbe SingletonThreadPool di default (5).
    engine, _ = encrypted_engine
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        session.add(
            Dipendente(
                id="dip-concorrenza",
                nome="Anna",
                cognome="Bianchi",
                codice_fiscale="BNCNNA80A01A271Z",
                data_assunzione=datetime(2026, 1, 1),
                data_licenziamento=None,
                flg_attivo=True,
                flg_certificazione_gas=False,
            )
        )
        session.commit()

    errori = []

    def leggi(_):
        try:
            with session_factory() as session:
                assert session.get(Dipendente, "dip-concorrenza") is not None
        except Exception as errore:  # raccolto qui: dentro un worker thread pytest non lo vedrebbe
            errori.append(errore)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(leggi, range(30)))

    assert errori == []
