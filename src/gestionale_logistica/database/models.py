from sqlalchemy.orm import Mapped, mapped_column
from gestionale_logistica.database.base import Base


class Esempio(Base):
    __tablename__ = "esempio"
    id: Mapped[int] = mapped_column(primary_key=True)