from datetime import datetime

from gestionale_logistica.database.models import Camion, Dipendente
from gestionale_logistica.risorse.visualizza_risorse import VisualizzaRisorseAttive, VisualizzaStoricoRisorse


def crea_dipendente(id_, attivo=True):
    return Dipendente(
        id=id_,
        nome="Nome",
        cognome="Cognome",
        codice_fiscale=f"CF-{id_}",
        data_assunzione=datetime(2020, 1, 1),
        data_licenziamento=None if attivo else datetime(2026, 1, 1),
        flg_attivo=attivo,
        flg_certificazione_gas=False,
    )


def crea_camion(id_, attivo=True):
    return Camion(
        id=id_,
        targa=f"TARGA-{id_}",
        tipo_mezzo="Furgone",
        peso_massimo=100.0,
        volume_massimo=5.0,
        flg_sponda_idraulica=False,
        data_acquisizione=datetime(2020, 1, 1),
        data_dismissione=None if attivo else datetime(2026, 1, 1),
        flg_attivo=attivo,
    )


def popola_risorse_miste(session_factory):
    with session_factory() as session:
        session.add(crea_dipendente("D1", attivo=True))
        session.add(crea_dipendente("D2", attivo=False))
        session.add(crea_camion("C1", attivo=True))
        session.add(crea_camion("C2", attivo=False))
        session.commit()


def test_visualizza_risorse_attive_esclude_licenziati_e_dismessi(session_factory):
    popola_risorse_miste(session_factory)

    elenco = VisualizzaRisorseAttive(session_factory).elenca()

    assert {d.id for d in elenco.dipendenti} == {"D1"}
    assert {c.id for c in elenco.camion} == {"C1"}


def test_visualizza_risorse_attive_su_db_vuoto(session_factory):
    elenco = VisualizzaRisorseAttive(session_factory).elenca()

    assert elenco.dipendenti == []
    assert elenco.camion == []


def test_visualizza_storico_risorse_include_attivi_e_licenziati_dismessi(session_factory):
    popola_risorse_miste(session_factory)

    elenco = VisualizzaStoricoRisorse(session_factory).elenca()

    assert {d.id for d in elenco.dipendenti} == {"D1", "D2"}
    assert {c.id for c in elenco.camion} == {"C1", "C2"}

    d2 = next(d for d in elenco.dipendenti if d.id == "D2")
    assert d2.flg_attivo is False
    c2 = next(c for c in elenco.camion if c.id == "C2")
    assert c2.flg_attivo is False


def test_visualizza_storico_risorse_su_db_vuoto(session_factory):
    elenco = VisualizzaStoricoRisorse(session_factory).elenca()

    assert elenco.dipendenti == []
    assert elenco.camion == []
