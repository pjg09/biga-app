from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import NotificationStatus, NotificationType


class NotificationLog(Base):
    __tablename__ = "notifications_log"
    __table_args__ = (Index("idx_notifications_status", "institution_id", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, native_enum=True, name="notification_type"), nullable=False
    )
    student_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    guardian_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("guardians.id"), nullable=False)
    email_to: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, native_enum=True, name="notification_status"),
        nullable=False,
        server_default="PENDING",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
