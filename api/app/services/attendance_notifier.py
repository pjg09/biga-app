import logging
from datetime import datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.core.config import settings
from app.models.enums import AttendanceStatus, NotificationStatus, NotificationType
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


def _build_html(student_name: str, group_name: str | None, grade_name: str | None, absence_date, link: str) -> str:
    class_label = " ".join(p for p in (grade_name, group_name) if p)
    group_line = f" del grupo {class_label}" if class_label else ""
    date_str = absence_date.strftime("%d/%m/%Y")
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Reporte de inasistencia</h2>
  <p>El/La estudiante <strong>{student_name}</strong>{group_line} no asistió a la primera
  hora de clase el día <strong>{date_str}</strong>.</p>
  <p>Si la ausencia tiene una justificación, puede registrarla en el siguiente enlace.
  Es de un solo uso y vence al final del día:</p>
  <p style="text-align: center; margin: 28px 0;">
    <a href="{link}" style="background: #4A0A9E; color: #fff; padding: 12px 28px;
       border-radius: 10px; text-decoration: none; font-weight: 600;">Justificar inasistencia</a>
  </p>
  <p style="font-size: 13px; color: #6b6880;">Si el botón no funciona, copie y pegue este enlace:<br>{link}</p>
</div>"""


class AttendanceNotifier:
    """Lado de job: notifica la inasistencia de primera hora al acudiente.

    Construye sus repositorios desde la sesión que le inyecta el runner del job.
    """

    def __init__(self, session: AsyncSession, email: EmailAdapter):
        self.session = session
        self.repo = AttendanceRepository(session)
        self.guardian_repo = GuardianRepository(session)
        self.notif_repo = NotificationRepository(session)
        self.email = email

    async def notify_absence(self, record_id: UUID) -> None:
        ctx = await self.repo.get_context(record_id)
        if not ctx:
            logger.warning("Registro de asistencia %s no existe; no se notifica", record_id)
            return

        record = ctx.record
        # El estudiante llegó (tardanza), ya fue justificado o corregido a presente.
        if record.status != AttendanceStatus.ABSENT:
            return

        # Idempotencia: un token por registro. Si ya existe, ya se notificó.
        if await self.repo.get_token_by_record(record_id):
            return

        guardian = await self.guardian_repo.get_primary(record.student_id)
        if not guardian:
            logger.error(
                "Estudiante %s sin acudiente primario; no se notifica inasistencia",
                record.student_id,
            )
            return

        token_value = uuid4()
        expires_at = datetime.combine(record.date + timedelta(days=1), time.min)
        await self.repo.create_token(
            token_id=uuid4(),
            record_id=record_id,
            token=token_value,
            expires_at=expires_at,
        )

        student_name = f"{ctx.student.first_name} {ctx.student.last_name}"
        link = f"{settings.frontend_url.rstrip('/')}/justificar/{token_value}"
        subject = f"Inasistencia de {student_name}"
        html = _build_html(student_name, ctx.group_name, ctx.grade_name, record.date, link)

        # Visibilidad en dev/demo: sin una API key real de Resend el correo no
        # sale, pero el enlace queda en los logs del worker para probar el flujo.
        logger.info("Enlace de justificación para %s: %s", student_name, link)

        notif_status = NotificationStatus.SENT
        error_message = None
        sent_at = datetime.now()
        try:
            self.email.send(guardian.email, subject, html)
        except Exception as exc:  # noqa: BLE001 — fallo de correo no debe romper el job
            notif_status = NotificationStatus.FAILED
            error_message = str(exc)
            sent_at = None
            logger.exception("Fallo enviando correo de inasistencia para %s", record.student_id)

        await self.notif_repo.create_log(
            institution_id=record.institution_id,
            type=NotificationType.ABSENCE_FIRST_HOUR,
            student_id=record.student_id,
            guardian_id=guardian.id,
            email_to=guardian.email,
            subject=subject,
            status=notif_status,
            error_message=error_message,
            sent_at=sent_at,
        )
