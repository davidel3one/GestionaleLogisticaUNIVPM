import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Enum, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gestionale_logistica.database.base import Base
from gestionale_logistica.database.enums import (
    CategoriaConsegna,
    RuoloUtente,
    StatoEsito,
    StatoOrdine,
    StatoViaggio,
)


def _enum_column(enum_cls: type[enum.Enum]):
    return mapped_column(Enum(enum_cls, values_callable=lambda obj: [e.value for e in obj]))


class Dipendente(Base):
    __tablename__ = "dipendenti"

    id: Mapped[str] = mapped_column(primary_key=True)
    nome: Mapped[str]
    cognome: Mapped[str]
    codice_fiscale: Mapped[str] = mapped_column(unique=True)
    data_assunzione: Mapped[datetime]
    data_licenziamento: Mapped[Optional[datetime]]
    attivo: Mapped[bool]
    certificazione_gas: Mapped[bool]


class Camion(Base):
    __tablename__ = "camion"

    id: Mapped[str] = mapped_column(primary_key=True)
    targa: Mapped[str] = mapped_column(unique=True)
    tipo_mezzo: Mapped[str]
    sponda_idraulica: Mapped[bool]
    data_acquisizione: Mapped[datetime]
    data_dismissione: Mapped[Optional[datetime]]
    attivo: Mapped[bool]


class Squadra(Base):
    __tablename__ = "squadre"

    id: Mapped[str] = mapped_column(primary_key=True)
    attiva: Mapped[bool]
    data_creazione: Mapped[datetime]

    composizioni: Mapped[list["ComposizioneSquadra"]] = relationship(back_populates="squadra")


class ComposizioneSquadra(Base):
    """Formazione storicizzata (squadra+camion+2 dipendenti) valida in un intervallo di date; unico modo per risalire ai membri di una Squadra (Fix 5)."""

    __tablename__ = "composizioni_squadra"

    id_composizione: Mapped[str] = mapped_column(primary_key=True)
    squadra_id: Mapped[str] = mapped_column(ForeignKey("squadre.id"))
    camion_id: Mapped[str] = mapped_column(ForeignKey("camion.id"))
    dipendente_1_id: Mapped[str] = mapped_column(ForeignKey("dipendenti.id"))
    dipendente_2_id: Mapped[str] = mapped_column(ForeignKey("dipendenti.id"))
    data_inizio_validita: Mapped[datetime]
    data_fine_validita: Mapped[Optional[datetime]]
    attiva: Mapped[bool]

    squadra: Mapped["Squadra"] = relationship(back_populates="composizioni")
    camion: Mapped["Camion"] = relationship()
    dipendente_1: Mapped["Dipendente"] = relationship(foreign_keys=[dipendente_1_id])
    dipendente_2: Mapped["Dipendente"] = relationship(foreign_keys=[dipendente_2_id])
    viaggi: Mapped[list["Viaggio"]] = relationship(back_populates="composizione")


class Viaggio(Base):
    __tablename__ = "viaggi"

    id: Mapped[str] = mapped_column(primary_key=True)
    data_partenza_prevista: Mapped[datetime]
    data_arrivo_prevista: Mapped[datetime]
    km_percorsi: Mapped[Optional[float]]
    stato_viaggio: Mapped[StatoViaggio] = _enum_column(StatoViaggio)
    composizione_id: Mapped[str] = mapped_column(ForeignKey("composizioni_squadra.id_composizione"))

    composizione: Mapped["ComposizioneSquadra"] = relationship(back_populates="viaggi")
    ordini: Mapped[list["Ordine"]] = relationship(back_populates="viaggio")


class Ordine(Base):
    __tablename__ = "ordini"

    id: Mapped[str] = mapped_column(primary_key=True)
    destinazione: Mapped[str]
    cliente: Mapped[str]
    peso: Mapped[float]
    volume_cargo: Mapped[float]
    categoria_consegna: Mapped[CategoriaConsegna] = _enum_column(CategoriaConsegna)
    stato_ordine: Mapped[StatoOrdine] = _enum_column(StatoOrdine)
    data_consegna: Mapped[Optional[datetime]]
    viaggio_id: Mapped[Optional[str]] = mapped_column(ForeignKey("viaggi.id"))

    viaggio: Mapped[Optional["Viaggio"]] = relationship(back_populates="ordini")
    esito: Mapped[Optional["EsitoConsegna"]] = relationship(back_populates="ordine")


class CausaleFallimento(Base):
    __tablename__ = "causali_fallimento"

    codice: Mapped[str] = mapped_column(primary_key=True)
    descrizione: Mapped[str]


class RegistroEsiti(Base):
    __tablename__ = "registri_esiti"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_riferimento: Mapped[datetime] = mapped_column(unique=True)

    esiti: Mapped[list["EsitoConsegna"]] = relationship(back_populates="registro")


class EsitoConsegna(Base):
    __tablename__ = "esiti_consegna"

    id: Mapped[int] = mapped_column(primary_key=True)
    stato_esito: Mapped[StatoEsito] = _enum_column(StatoEsito)
    data_registrazione: Mapped[datetime]
    ordine_id: Mapped[str] = mapped_column(ForeignKey("ordini.id"), unique=True)
    causale_id: Mapped[Optional[str]] = mapped_column(ForeignKey("causali_fallimento.codice"))
    registro_id: Mapped[int] = mapped_column(ForeignKey("registri_esiti.id"))

    ordine: Mapped["Ordine"] = relationship(back_populates="esito")
    causale: Mapped[Optional["CausaleFallimento"]] = relationship()
    registro: Mapped["RegistroEsiti"] = relationship(back_populates="esiti")
    allegati: Mapped[list["Allegato"]] = relationship(back_populates="esito")


class Allegato(Base):
    __tablename__ = "allegati"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_file: Mapped[str]
    percorso_file: Mapped[str]
    tipo_file: Mapped[str]
    data_caricamento: Mapped[datetime]
    esito_id: Mapped[int] = mapped_column(ForeignKey("esiti_consegna.id"))

    esito: Mapped["EsitoConsegna"] = relationship(back_populates="allegati")


report_ordini = Table(
    "report_ordini",
    Base.metadata,
    Column("report_id", ForeignKey("report_consuntivi.id"), primary_key=True),
    Column("ordine_id", ForeignKey("ordini.id"), primary_key=True),
)


class ReportConsuntivo(Base):
    __tablename__ = "report_consuntivi"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_generazione: Mapped[datetime]
    ordini_consegnati: Mapped[int]
    ordini_falliti: Mapped[int]
    formato_output: Mapped[str]
    negozi_partner: Mapped[str]
    percorso_file: Mapped[str]
    registro_id: Mapped[int] = mapped_column(ForeignKey("registri_esiti.id"), unique=True)

    registro: Mapped["RegistroEsiti"] = relationship()
    ordini: Mapped[list["Ordine"]] = relationship(secondary=report_ordini)


class Utente(Base):
    __tablename__ = "utenti"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    cognome: Mapped[str]
    telefono: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    ruolo: Mapped[RuoloUtente] = _enum_column(RuoloUtente)
    email_confermata: Mapped[bool]
    data_registrazione: Mapped[datetime]


class CodiceConferma(Base):
    __tablename__ = "codici_conferma"

    id: Mapped[int] = mapped_column(primary_key=True)
    utente_id: Mapped[int] = mapped_column(ForeignKey("utenti.id"))
    codice: Mapped[str]
    data_scadenza: Mapped[datetime]
    tentativi_falliti: Mapped[int]


class Sessione(Base):
    __tablename__ = "sessioni"

    id: Mapped[int] = mapped_column(primary_key=True)
    utente_id: Mapped[int] = mapped_column(ForeignKey("utenti.id"))
    token: Mapped[str] = mapped_column(unique=True)
    data_creazione: Mapped[datetime]
    data_scadenza: Mapped[datetime]
