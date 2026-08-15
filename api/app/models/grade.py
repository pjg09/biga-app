from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Grade(Base):
    __tablename__ = "grades"
    # `name` también es único por institución (migración `b8d4f1a7c360`): el
    # select de Grado del alta de salones muestra solo el nombre, así que dos
    # grados homónimos serían indistinguibles al matricular.
    __table_args__ = (
        UniqueConstraint("institution_id", "level"),
        UniqueConstraint("institution_id", "name", name="uq_grades_institution_id_name"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
