from datetime import date as PyDate, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AttendanceStatus


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("student_id", "class_period_id", "date"),
        Index("idx_attendance_student_date", "student_id", "date"),
        Index("idx_attendance_group_date", "group_id", "date"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    class_period_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("class_periods.id"), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    recorded_by_user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[PyDate] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, native_enum=True, name="attendance_status"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AttendanceToken(Base):
    __tablename__ = "attendance_tokens"
    __table_args__ = (Index("idx_attendance_tokens_token", "token"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_record_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("attendance_records.id"), nullable=False, unique=True
    )
    token: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, unique=True, default=uuid4)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AttendanceJustification(Base):
    __tablename__ = "attendance_justifications"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_record_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("attendance_records.id"), nullable=False, unique=True
    )
    token_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("attendance_tokens.id"), nullable=False, unique=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
