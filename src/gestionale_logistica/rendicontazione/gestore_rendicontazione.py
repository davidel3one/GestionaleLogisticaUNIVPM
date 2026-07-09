from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import (
    Allegato,
    CausaleFallimento,
    EsitoConsegna,
    RegistroEsiti,
    ReportConsuntivo,
)

esito_consegna = CRUDBase[EsitoConsegna](EsitoConsegna)
causale_fallimento = CRUDBase[CausaleFallimento](CausaleFallimento)
registro_esiti = CRUDBase[RegistroEsiti](RegistroEsiti)
allegato = CRUDBase[Allegato](Allegato)
report_consuntivo = CRUDBase[ReportConsuntivo](ReportConsuntivo)
