from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import Camion

camion = CRUDBase[Camion](Camion)
