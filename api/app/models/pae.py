from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import PAEIdentificationMethod


class PAEEnrollment(Base):
    __tablename__ = "pae_enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year"),
        Index("idx_pae_enrollments_active", "institution_id", "academic_year", postgresql_where="is_active = TRUE"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    academic_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Fijado explícitamente por la app (no server_default) para incluirlo en el hash.
    enrolled_at: Mapped[datetime] = mapped_column(nullable=False)
    enrollment_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class PAEDelivery(Base):
    __tablename__ = "pae_deliveries"
    __table_args__ = (
        UniqueConstraint("student_id", "delivery_date"),
        Index("idx_pae_deliveries_date_institution", "institution_id", "delivery_date"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    delivered_by_user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    identification_method: Mapped[PAEIdentificationMethod] = mapped_column(
        SAEnum(PAEIdentificationMethod, native_enum=True, name="pae_identification_method"), nullable=False
    )
    delivery_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
