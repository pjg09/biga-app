import logging
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.models.enums import NotificationStatus, NotificationType
from app.repositories.notification_repository import NotificationRepository
from app.repositories.pae_repository import PAERepository

logger = logging.getLogger(__name__)


def _build_html(student_name: str, delivery_date: date) -> str:
    date_str = delivery_date.strftime("%d/%m/%Y")
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">El/La estudiante no reclamó el PAE</h2>
  <p>El/La estudiante <strong>{student_name}</strong> está inscrito/a en el Programa de
  Alimentación Escolar (PAE), pero <strong>no reclamó su alimento</strong> el día
  <strong>{date_str}</strong>.</p>
  <p style="font-size: 13px; color: #6b6880;">Si considera que se trata de un error,
  comuníquese con la institución.</p>
</div>"""


class PAENotifier:
    """Lado de job: notifica a los acudientes de estudiantes inscritos en el PAE
    que no reclamaron su alimento en el día.

    Construye sus repositorios desde la sesión que le inyecta el runner del job.
    """

    def __init__(self, session: AsyncSession, email: EmailAdapter):
        self.session = session
        self.repo = PAERepository(session)
        self.notif_repo = NotificationRepository(session)
        self.email = email

    async def notify_no_claims(self, institution_id: UUID, delivery_date: date) -> None:
        # Si no hubo NINGUNA entrega ese día, se asume que el PAE no operó (feriado,
        # sin servicio). Notificar en ese caso sería un falso positivo masivo.
        if await self.repo.count_deliveries_on(institution_id, delivery_date) == 0:
            logger.info(
                "Institución %s: 0 entregas PAE el %s; no se notifica (PAE no operó)",
                institution_id,
                delivery_date,
            )
            return

        academic_year = delivery_date.year
        pairs = await self.repo.get_no_claim_students_with_guardians(
            institution_id=institution_id,
            academic_year=academic_year,
            delivery_date=delivery_date,
        )
        if not pairs:
            return

        for student, guardian in pairs:
            student_name = f"{student.first_name} {student.last_name}"
            subject = f"{student_name} no reclamó el PAE hoy"
            html = _build_html(student_name, delivery_date)

            notif_status = NotificationStatus.SENT
            error_message = None
            sent_at = datetime.now()
            try:
                self.email.send(guardian.email, subject, html)
            except Exception as exc:  # noqa: BLE001 — un fallo de correo no debe romper el lote
                notif_status = NotificationStatus.FAILED
                error_message = str(exc)
                sent_at = None
                logger.exception(
                    "Fallo enviando correo de no reclamo PAE para %s", student.id
                )

            await self.notif_repo.create_log(
                institution_id=institution_id,
                type=NotificationType.PAE_NO_CLAIM,
                student_id=student.id,
                guardian_id=guardian.id,
                email_to=guardian.email,
                subject=subject,
                status=notif_status,
                error_message=error_message,
                sent_at=sent_at,
            )
