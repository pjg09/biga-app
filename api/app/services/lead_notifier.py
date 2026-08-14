import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.core.config import settings
from app.models.enums import NotificationStatus
from app.repositories.lead_repository import LeadRepository

logger = logging.getLogger(__name__)


def _build_html(email: str, created_at: datetime, source: str) -> str:
    when = created_at.strftime("%d/%m/%Y %H:%M")
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Nueva solicitud de demo</h2>
  <p>Alguien dejó su correo en el formulario de la landing:</p>
  <p style="font-size: 18px;"><strong>{email}</strong></p>
  <p style="font-size: 13px; color: #6b6880;">Recibida el {when} · origen: {source}</p>
</div>"""


class LeadNotifier:
    """Lado de job: avisa al buzón interno de una solicitud de demo.

    A diferencia del resto de notifiers, no escribe en `notifications_log` — esa
    tabla exige institution_id/student_id/guardian_id NOT NULL y un lead no tiene
    ninguno. El resultado del envío se guarda en el propio `demo_leads`.
    """

    def __init__(self, session: AsyncSession, email: EmailAdapter):
        self.session = session
        self.repo = LeadRepository(session)
        self.email = email

    async def notify(self, lead_id: UUID) -> None:
        lead = await self.repo.get_by_id(lead_id)
        if not lead:
            logger.warning("Lead %s no existe; no se notifica", lead_id)
            return

        subject = f"Nueva solicitud de demo: {lead.email}"
        html = _build_html(lead.email, lead.created_at, lead.source)

        try:
            self.email.send(settings.leads_notify_email, subject, html)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo enviando aviso de lead %s", lead_id)
            await self.repo.mark_notification(
                lead_id, NotificationStatus.FAILED, error_message=str(exc), sent_at=None
            )
            return

        await self.repo.mark_notification(
            lead_id, NotificationStatus.SENT, error_message=None, sent_at=datetime.now()
        )
