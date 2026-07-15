import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.models.enums import NotificationStatus, NotificationType
from app.repositories.departure_repository import DepartureRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


def _build_html(student_name: str, departure_date, departure_time, reason: str | None) -> str:
    date_str = departure_date.strftime("%d/%m/%Y")
    time_str = departure_time.strftime("%H:%M")
    reason_block = (
        f'<p>Motivo registrado: <em>{reason}</em></p>' if reason else ""
    )
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Salida anticipada</h2>
  <p>Se registró la salida anticipada del/de la estudiante <strong>{student_name}</strong>
  el día <strong>{date_str}</strong> a las <strong>{time_str}</strong>.</p>
  {reason_block}
  <p style="font-size: 13px; color: #6b6880;">Si no autorizó esta salida, comuníquese
  de inmediato con la institución.</p>
</div>"""


class DepartureNotifier:
    """Lado de job: notifica al acudiente la salida anticipada del estudiante."""

    def __init__(self, session: AsyncSession, email: EmailAdapter):
        self.session = session
        self.repo = DepartureRepository(session)
        self.guardian_repo = GuardianRepository(session)
        self.notif_repo = NotificationRepository(session)
        self.email = email

    async def notify(self, departure_id: UUID) -> None:
        ctx = await self.repo.get_context(departure_id)
        if not ctx:
            logger.warning("Salida anticipada %s no existe; no se notifica", departure_id)
            return

        departure = ctx.departure
        guardian = await self.guardian_repo.get_primary(departure.student_id)
        if not guardian:
            logger.error(
                "Estudiante %s sin acudiente primario; no se notifica salida anticipada",
                departure.student_id,
            )
            return

        student_name = f"{ctx.student.first_name} {ctx.student.last_name}"
        subject = f"Salida anticipada de {student_name}"
        html = _build_html(student_name, departure.departure_date, departure.departure_time, departure.reason)

        notif_status = NotificationStatus.SENT
        error_message = None
        sent_at = datetime.now()
        try:
            self.email.send(guardian.email, subject, html)
        except Exception as exc:  # noqa: BLE001
            notif_status = NotificationStatus.FAILED
            error_message = str(exc)
            sent_at = None
            logger.exception("Fallo enviando correo de salida anticipada para %s", departure.student_id)

        await self.notif_repo.create_log(
            institution_id=departure.institution_id,
            type=NotificationType.EARLY_DEPARTURE,
            student_id=departure.student_id,
            guardian_id=guardian.id,
            email_to=guardian.email,
            subject=subject,
            status=notif_status,
            error_message=error_message,
            sent_at=sent_at,
        )
