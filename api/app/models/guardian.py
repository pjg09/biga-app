from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import GuardianRelationship


class Guardian(Base):
    __tablename__ = "guardians"
    __table_args__ = (
        Index(
            "one_primary_per_student",
            "student_id",
            unique=True,
            postgresql_where="is_primary = TRUE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship: Mapped[GuardianRelationship] = mapped_column(
        SAEnum(GuardianRelationship, native_enum=True, name="guardian_relationship"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
