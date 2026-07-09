from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestionale_logistica.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    """Operazioni Create/Read/Update/Delete generiche per un modello SQLAlchemy."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Ottiene un singolo record tramite la chiave primaria."""
        return db.get(self.model, id)

    def get_all(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Ottiene una lista di record con supporto per paginazione."""
        stmt = select(self.model).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Crea un nuovo record nel database."""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Aggiorna un record esistente."""
        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Elimina un record tramite la chiave primaria."""
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
