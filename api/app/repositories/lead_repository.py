from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus
from app.models.lead import DemoLead


class LeadRepository:
    """Acceso a `demo_leads`.

    Es la única tabla sin `institution_id` del proyecto, así que ningún método
    de aquí recibe ni filtra por tenant. Ver `docs/database-schema.md`.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, lead: DemoLead) -> DemoLead:
        self.session.add(lead)
        await self.session.flush()
        await self.session.refresh(lead)
        return lead

    async def get_by_id(self, lead_id: UUID) -> DemoLead | None:
        result = await self.session.execute(select(DemoLead).where(DemoLead.id == lead_id))
        return result.scalar_one_or_none()

    async def count_recent_by_email(self, email: str, since: datetime) -> int:
        """Cuántas solicitudes hizo ese correo desde `since` (incluida la actual)."""
        result = await self.session.execute(
            select(func.count())
            .select_from(DemoLead)
            .where(DemoLead.email == email, DemoLead.created_at >= since)
        )
        return result.scalar_one()

    async def mark_notification(
        self,
        lead_id: UUID,
        status: NotificationStatus,
        error_message: str | None = None,
        sent_at: datetime | None = None,
    ) -> None:
        lead = await self.get_by_id(lead_id)
        if lead is None:
            return
        lead.notification_status = status
        lead.notification_error = error_message
        lead.notified_at = sent_at
