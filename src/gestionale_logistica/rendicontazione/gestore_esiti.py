import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from gestionale_logistica.database.base import SessionLocal
from gestionale_logistica.database.enums import StatoEsito, StatoOrdine, StatoViaggio
from gestionale_logistica.database.models import (
    Allegato,
    CausaleFallimento,
    EsitoConsegna,
    Ordine,
    RegistroEsiti,
)

CARTELLA_ALLEGATI_DEFAULT = Path("allegati")


@dataclass
class RisultatoRegistrazioneEsito:
    ok: bool
    esito_id: int | None = None
    motivo: str | None = None


@dataclass
class RisultatoOperazione:
    ok: bool
    motivo: str | None = None


class GestoreEsiti:
    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        cartella_allegati: Path = CARTELLA_ALLEGATI_DEFAULT,
    ) -> None:
        self.session_factory = session_factory
        self.cartella_allegati = cartella_allegati

    def registra_esito(
        self,
        ordine_id: str,
        stato_esito: StatoEsito,
        causale_codice: str | None = None,
    ) -> RisultatoRegistrazioneEsito:
        """RF16: registra l'esito di consegna di un ordine in transito. RF17 (automatico, non
        un passo separato): se l'esito e' Fallito, l'ordine torna RICEVUTO e sganciato dal
        viaggio (viaggio_id=None), il che lo rimette tra i candidati di
        MotoreOttimizzazione.suggerisci_ordini/calcola_piano.
        """
        with self.session_factory() as session:
            ordine = session.get(Ordine, ordine_id)
            if ordine is None:
                return RisultatoRegistrazioneEsito(ok=False, motivo=f"Ordine '{ordine_id}' non trovato")
            if ordine.esito is not None:
                return RisultatoRegistrazioneEsito(ok=False, motivo="Ordine gia' associato a un esito")
            if ordine.viaggio is None or ordine.viaggio.stato_viaggio != StatoViaggio.IN_CORSO:
                return RisultatoRegistrazioneEsito(
                    ok=False, motivo="L'ordine non e' su un viaggio in corso"
                )

            if stato_esito == StatoEsito.FALLITO:
                if causale_codice is None:
                    return RisultatoRegistrazioneEsito(
                        ok=False, motivo="Causale obbligatoria per un esito Fallito"
                    )
                if session.get(CausaleFallimento, causale_codice) is None:
                    return RisultatoRegistrazioneEsito(
                        ok=False, motivo=f"Causale '{causale_codice}' non trovata"
                    )

            # Raggruppamento per giorno di PARTENZA del viaggio (non per oggi): stesso criterio
            # usato da calcola_piano (RF13), per non creare un RegistroEsiti disallineato quando
            # l'esito viene registrato un giorno dopo la partenza.
            partenza = ordine.viaggio.data_partenza_prevista
            data_riferimento = datetime(partenza.year, partenza.month, partenza.day)
            registro = session.scalar(
                select(RegistroEsiti).where(RegistroEsiti.data_riferimento == data_riferimento)
            )
            if registro is None:
                registro = RegistroEsiti(data_riferimento=data_riferimento)
                session.add(registro)
                session.flush()

            esito = EsitoConsegna(
                stato_esito=stato_esito,
                data_registrazione=datetime.now(),
                ordine_id=ordine_id,
                causale_id=causale_codice if stato_esito == StatoEsito.FALLITO else None,
                registro_id=registro.id,
            )
            session.add(esito)

            ordine.data_consegna = datetime.now()
            if stato_esito == StatoEsito.COMPLETATO:
                ordine.stato_ordine = StatoOrdine.COMPLETATO
            else:
                ordine.stato_ordine = StatoOrdine.RICEVUTO
                ordine.viaggio_id = None

            session.commit()
            return RisultatoRegistrazioneEsito(ok=True, esito_id=esito.id)

    def carica_prova_documentale(
        self,
        esito_id: int,
        nome_file: str,
        percorso_file_originale: str,
        tipo_file: str,
    ) -> RisultatoOperazione:
        """RF18: copia FISICAMENTE il file (non solo il riferimento al percorso originale) in
        cartella_allegati/<esito_id>/<nome_file>, cosi' la prova documentale non si perde se
        l'utente sposta o cancella il file sorgente dopo il caricamento.
        """
        with self.session_factory() as session:
            esito = session.get(EsitoConsegna, esito_id)
            if esito is None:
                return RisultatoOperazione(ok=False, motivo=f"Esito '{esito_id}' non trovato")
            if esito.stato_esito != StatoEsito.FALLITO:
                return RisultatoOperazione(
                    ok=False, motivo="Le prove documentali si allegano solo a un esito Fallito"
                )

            origine = Path(percorso_file_originale)
            if not origine.is_file():
                return RisultatoOperazione(ok=False, motivo=f"File non trovato: {percorso_file_originale}")

            # Path(...).name scarta qualunque componente di percorso (".." o assoluto incluso):
            # previene path traversal / scrittura fuori da cartella_allegati (RF18 riceve un
            # nome_file che in futuro arrivera' da input utente via GUI, non ancora vincolato qui).
            nome_base = Path(nome_file).name
            if not nome_base:
                return RisultatoOperazione(ok=False, motivo="Nome file non valido")

            cartella_esito = self.cartella_allegati / str(esito_id)
            cartella_esito.mkdir(parents=True, exist_ok=True)
            # Prefisso univoco: due prove caricate con lo stesso nome file (es. "foto.jpg" da
            # fotocamere diverse) non devono sovrascriversi silenziosamente sul disco.
            destinazione = cartella_esito / f"{uuid.uuid4().hex[:8]}_{nome_base}"
            shutil.copy2(origine, destinazione)

            try:
                session.add(
                    Allegato(
                        nome_file=nome_file,
                        percorso_file=str(destinazione),
                        tipo_file=tipo_file,
                        data_caricamento=datetime.now(),
                        esito_id=esito_id,
                    )
                )
                session.commit()
            except Exception:
                destinazione.unlink(missing_ok=True)
                raise
            return RisultatoOperazione(ok=True)
