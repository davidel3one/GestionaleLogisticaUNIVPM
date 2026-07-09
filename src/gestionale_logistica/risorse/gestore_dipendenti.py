from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import Dipendente

dipendente = CRUDBase[Dipendente](Dipendente)
