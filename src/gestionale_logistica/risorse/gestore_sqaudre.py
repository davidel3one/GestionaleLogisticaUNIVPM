from gestionale_logistica.database.crud_base import CRUDBase
from gestionale_logistica.database.models import ComposizioneSquadra, Squadra

squadra = CRUDBase[Squadra](Squadra)
composizione_squadra = CRUDBase[ComposizioneSquadra](ComposizioneSquadra)
