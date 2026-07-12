from pathlib import Path

from gestionale_logistica.database.enums import CategoriaConsegna, StatoOrdine
from gestionale_logistica.database.models import Ordine
from gestionale_logistica.logistica.gestore_logistica import GestoreLogistica

DATI_ESEMPIO = Path(__file__).parent.parent / "dati_esempio"


def test_import_file_valido(session_factory):
    gestore = GestoreLogistica(session_factory)

    risultato = gestore.importa_ordini(DATI_ESEMPIO / "Ordini_Unieuro_20260706.csv")

    assert risultato.ordini_creati == 30
    assert risultato.errori == []

    with session_factory() as session:
        ordine = session.get(Ordine, "UNI-2026-0001")
        assert ordine is not None
        assert ordine.indirizzo == "Via Verdi 17"
        assert ordine.comune == "Fabriano"
        assert ordine.provincia == "AN"
        assert ordine.lat is not None
        assert ordine.lon is not None
        assert ordine.cliente == "Marco Rossi"
        assert ordine.peso == 32.1
        assert ordine.volume_cargo == 0.1
        assert ordine.categoria_consegna == CategoriaConsegna.BORDO_STRADA
        assert ordine.stato_ordine == StatoOrdine.RICEVUTO
        assert ordine.data_consegna is None
        assert ordine.viaggio_id is None


def test_riga_malformata_viene_scartata(tmp_path, session_factory):
    csv_path = tmp_path / "ordini_malformati.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Ancona;BordoStrada;10.5;0.2;AN\n"
        "ORD-002;Luca Neri;Via Milano 2, Ancona;BordoStrada;non-numerico;0.3;AN\n"
        "ORD-003;Anna Verdi;Via Torino 3, Ancona;Incasso;15.0;0.4;AN\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 2
    assert len(risultato.errori) == 1
    assert risultato.errori[0].riga == 3

    with session_factory() as session:
        assert session.get(Ordine, "ORD-001") is not None
        assert session.get(Ordine, "ORD-002") is None
        assert session.get(Ordine, "ORD-003") is not None


def test_riga_con_colonne_mancanti_viene_scartata_senza_interrompere(tmp_path, session_factory):
    # Una riga con meno colonne dell'header non deve far crashare l'intero import (RF9):
    # va scartata e riportata come errore, lasciando importare le righe valide successive.
    csv_path = tmp_path / "ordini_colonne_mancanti.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Ancona;BordoStrada;10.5;0.2;AN\n"
        "ORD-002;Luca Neri;Via Milano 2, Ancona;BordoStrada\n"
        "ORD-003;Anna Verdi;Via Torino 3, Ancona;Incasso;15.0;0.4;AN\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 2
    assert len(risultato.errori) == 1
    assert risultato.errori[0].riga == 3

    with session_factory() as session:
        assert session.get(Ordine, "ORD-001") is not None
        assert session.get(Ordine, "ORD-002") is None
        assert session.get(Ordine, "ORD-003") is not None


def test_riga_manca_solo_provincia_viene_scartata_senza_interrompere(tmp_path, session_factory):
    # Variante del caso "colonne mancanti" in cui manca SOLO l'ultima colonna (Provincia):
    # Categoria/Peso/Volume sono presenti e superano il parsing, quindi il TypeError non
    # scatta e riga["Provincia"] resta None. Non deve far crashare l'import con
    # AttributeError su None.strip(): va scartata come errore, importando le righe valide.
    csv_path = tmp_path / "ordini_manca_provincia.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Ancona;BordoStrada;10.5;0.2;AN\n"
        "ORD-002;Luca Neri;Via Milano 2, Ancona;BordoStrada;10.5;0.2\n"
        "ORD-003;Anna Verdi;Via Torino 3, Ancona;Incasso;15.0;0.4;AN\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 2
    assert len(risultato.errori) == 1
    assert risultato.errori[0].riga == 3

    with session_factory() as session:
        assert session.get(Ordine, "ORD-001") is not None
        assert session.get(Ordine, "ORD-002") is None
        assert session.get(Ordine, "ORD-003") is not None


def test_indirizzo_senza_virgola_viene_scartato(tmp_path, session_factory):
    csv_path = tmp_path / "ordini_indirizzo_malformato.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1 Ancona;BordoStrada;10.5;0.2;AN\n"
        "ORD-002;Anna Verdi;Via Torino 3, Ancona;Incasso;15.0;0.4;AN\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 1
    assert len(risultato.errori) == 1
    assert risultato.errori[0].riga == 2

    with session_factory() as session:
        assert session.get(Ordine, "ORD-001") is None
        assert session.get(Ordine, "ORD-002") is not None


def test_comune_non_geocodificabile_importa_senza_coordinate(tmp_path, session_factory):
    csv_path = tmp_path / "ordini_comune_sconosciuto.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Comuneinesistentexyz;BordoStrada;10.5;0.2;ZZ\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 1
    assert risultato.errori == []

    with session_factory() as session:
        ordine = session.get(Ordine, "ORD-001")
        assert ordine is not None
        assert ordine.comune == "Comuneinesistentexyz"
        assert ordine.provincia == "ZZ"
        assert ordine.lat is None
        assert ordine.lon is None


def test_id_ordine_duplicato_viene_scartato(tmp_path, session_factory):
    with session_factory() as session:
        session.add(
            Ordine(
                id="ORD-001",
                indirizzo="Via Esistente 1",
                comune="Ancona",
                provincia="AN",
                lat=None,
                lon=None,
                cliente="Cliente Esistente",
                peso=1.0,
                volume_cargo=0.1,
                categoria_consegna=CategoriaConsegna.BORDO_STRADA,
                stato_ordine=StatoOrdine.RICEVUTO,
                data_consegna=None,
                viaggio_id=None,
            )
        )
        session.commit()

    csv_path = tmp_path / "ordini_duplicati.csv"
    csv_path.write_text(
        "ID_Ordine;Cliente;Indirizzo;Categoria;Peso;Volume;Provincia\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Ancona;BordoStrada;10.5;0.2;AN\n"
        "ORD-002;Luca Neri;Via Milano 2, Ancona;Incasso;15.0;0.4;AN\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 1
    assert len(risultato.errori) == 1
    assert risultato.errori[0].riga == 2

    with session_factory() as session:
        ordine_esistente = session.get(Ordine, "ORD-001")
        assert ordine_esistente.cliente == "Cliente Esistente"
        assert session.get(Ordine, "ORD-002") is not None


def test_header_non_riconosciuto_rifiuta_intero_file(tmp_path, session_factory):
    csv_path = tmp_path / "ordini_header_errato.csv"
    csv_path.write_text(
        "Codice;Cliente;Indirizzo;Categoria;Peso;Volume\n"
        "ORD-001;Mario Bianchi;Via Roma 1, Ancona;BordoStrada;10.5;0.2\n"
    )

    gestore = GestoreLogistica(session_factory)
    risultato = gestore.importa_ordini(csv_path)

    assert risultato.ordini_creati == 0
    assert len(risultato.errori) == 1

    with session_factory() as session:
        assert session.get(Ordine, "ORD-001") is None
