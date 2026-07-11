import enum


class CategoriaConsegna(enum.Enum):
    BORDO_STRADA = "BordoStrada"
    INSTALLAZIONE_SEMPLICE_AL_PIANO = "InstallazioneSempliceAlPiano"
    INCASSO = "Incasso"
    BIG = "Big"
    CERTIFICAZIONE_GAS = "CertificazioneGas"


class StatoOrdine(enum.Enum):
    RICEVUTO = "Ricevuto"
    PIANIFICATO = "Pianificato"
    IN_CONSEGNA = "InConsegna"
    COMPLETATO = "Completato"
    FALLITO = "Fallito"


class StatoViaggio(enum.Enum):
    IN_COMPOSIZIONE = "InComposizione"
    PIANIFICATO = "Pianificato"
    IN_CORSO = "InCorso"
    COMPLETATO = "Completato"
    ANNULLATO = "Annullato"


class StatoEsito(enum.Enum):
    COMPLETATO = "Completato"
    FALLITO = "Fallito"


class RuoloUtente(enum.Enum):
    ADMIN = "Admin"
