from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import NotificationStatus


class DemoLead(Base):
    """Solicitud de demo enviada desde el formulario público de la landing.

    Única tabla sin `institution_id` del proyecto, por decisión explícita: quien
    pide una demo todavía no pertenece a ninguna institución. Es pre-tenant y no
    la lee ningún flujo autenticado. Ver `docs/database-schema.md`.
    """

    __tablename__ = "demo_leads"
    __table_args__ = (
        Index("idx_demo_leads_created", "created_at"),
        Index("idx_demo_leads_email_created", "email", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="LANDING_CTA")
    notification_status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, native_enum=True, name="notification_status"),
        nullable=False,
        server_default="PENDING",
    )
    notification_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
