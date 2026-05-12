from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("institution_id", "level"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
