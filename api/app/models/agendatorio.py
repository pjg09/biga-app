from datetime import date as PyDate, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ArticleSeverity


class ConvivenciaArticle(Base):
    __tablename__ = "convivencia_articles"
    __table_args__ = (UniqueConstraint("institution_id", "code"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[ArticleSeverity] = mapped_column(
        SAEnum(ArticleSeverity, native_enum=True, name="article_severity"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class DisciplineRecord(Base):
    __tablename__ = "discipline_records"
    __table_args__ = (Index("idx_discipline_student", "student_id", "date"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    recorded_by_user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[PyDate] = mapped_column(nullable=False)
    observations: Mapped[str] = mapped_column(Text, nullable=False)
    signature_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class DisciplineRecordArticle(Base):
    __tablename__ = "discipline_record_articles"

    discipline_record_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("discipline_records.id"), primary_key=True
    )
    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("convivencia_articles.id"), primary_key=True
    )
