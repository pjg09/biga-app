from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (UniqueConstraint("student_id", "academic_year"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    academic_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
