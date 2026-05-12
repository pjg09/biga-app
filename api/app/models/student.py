from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("institution_id", "document_number"),
        Index("idx_students_document", "institution_id", "document_number"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    document_number: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
