from datetime import date as PyDate, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

    # Cierre del caso de seguimiento de una inasistencia SIN justificar. No es
    # `archived_at` a propósito: el registro de asistencia sigue contando en
    # Asistencia, en el roster y en las estadísticas. Lo único que se cierra es
    # el seguimiento del docente en la sección "Inasistencias".
    absence_closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


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

    # Soporte opcional que adjunta el acudiente (PDF o imagen). Las cuatro
    # columnas viajan juntas: o hay adjunto y están las cuatro, o no hay y son
    # nulas. Se guarda la KEY del objeto, no una URL: las presignadas caducan.
    attachment_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attachment_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attachment_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Caso cerrado por el docente. Mismo mecanismo que discipline_records: se
    # oculta del panel por defecto, nunca se borra.
    archived_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AttendanceAbsenceNote(Base):
    """Nota del docente sobre una inasistencia sin justificar. Append-only.

    Cuelga del registro de asistencia, no de la justificación: precisamente
    existe para los casos en los que el acudiente nunca usó el enlace. Si más
    tarde lo usa, la nota sobrevive aunque el caso pase a Mensajes.
    """

    __tablename__ = "attendance_absence_notes"
    __table_args__ = (Index("idx_absence_notes_record", "attendance_record_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_record_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("attendance_records.id"), nullable=False
    )
    institution_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class AttendanceJustificationNote(Base):
    """Nota de seguimiento sobre una excusa. Append-only: no se edita ni borra."""

    __tablename__ = "attendance_justification_notes"
    __table_args__ = (
        Index("idx_justification_notes_justification", "justification_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    justification_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("attendance_justifications.id"), nullable=False
    )
    institution_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
