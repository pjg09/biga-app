import logging
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.core.config import settings
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


def _build_correction_html(student_name: str, delivery_date: date) -> str:
    date_str = delivery_date.strftime("%d/%m/%Y")
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Corrección: el/la estudiante sí reclamó el PAE</h2>
  <p>Le informamos que el correo anterior sobre el/la estudiante <strong>{student_name}</strong>
  del día <strong>{date_str}</strong> fue un error: el registro llegó a la institución después
  de nuestro corte administrativo, pero <strong>sí reclamó su alimento</strong> ese día.</p>
  <p style="font-size: 13px; color: #6b6880;">Lamentamos la confusión.</p>
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
        """Prepara los avisos de no reclamo del día y los **encola uno a uno**.

        Antes recorría los pares enviando en bucle dentro del propio job. Con 14
        inscritos, Mailtrap rechazó 12 con `550 Too many emails per second`, y un
        `FAILED` no se reintenta ni se puede reenviar desde ninguna pantalla: esos
        12 avisos se perdían. Ahora cada correo es su propia tarea, con la salida
        escalonada (`notification_spacing_seconds`), de modo que el proveedor
        recibe un goteo en vez de una ráfaga y el fallo de uno no arrastra al resto.

        La fila de `notifications_log` se crea **aquí, como PENDING**, no al
        enviar. Es lo que hace idempotente al barrido, que corre cada 15 minutos:
        con 300 inscritos los últimos correos salen varios minutos después, y sin
        una marca previa el barrido siguiente los volvería a encolar.
        """
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

        # Import local: `app.jobs` importa Celery, y este service lo usan también
        # los tests, que no deben arrastrar el broker.
        from app.jobs.pae_jobs import send_pae_no_claim_email

        espaciado = settings.notification_spacing_seconds
        for i, (student, guardian) in enumerate(pairs):
            student_name = f"{student.first_name} {student.last_name}"
            log = await self.notif_repo.create_log(
                institution_id=institution_id,
                type=NotificationType.PAE_NO_CLAIM,
                student_id=student.id,
                guardian_id=guardian.id,
                email_to=guardian.email,
                subject=f"{student_name} no reclamó el PAE hoy",
                status=NotificationStatus.PENDING,
            )
            send_pae_no_claim_email.apply_async(
                (str(log.id), str(institution_id), str(student.id), delivery_date.isoformat()),
                countdown=round(i * espaciado, 2),
            )

    async def send_no_claim_email(
        self, log_id: UUID, institution_id: UUID, student_id: UUID, delivery_date: date
    ) -> None:
        """Envía **un** aviso ya encolado y cierra su fila de `notifications_log`.

        Relee el estado antes de enviar, igual que el job de inasistencia: entre
        el encolado y su turno pueden pasar minutos, y si el estudiante reclamó
        en ese rato el correo sería falso. En ese caso la notificación se marca
        `SUPPRESSED` — no se intentó a propósito, que es distinto de fallar.
        """
        log = await self.notif_repo.get_log(log_id)
        if not log or log.status != NotificationStatus.PENDING:
            return   # otro intento ya la cerró

        if await self.repo.has_delivery_on(student_id, institution_id, delivery_date):
            logger.info(
                "Estudiante %s reclamó antes de que saliera el aviso; se suprime", student_id
            )
            await self.notif_repo.mark_result(log, NotificationStatus.SUPPRESSED)
            return

        student = await self.repo.get_active_student(student_id, institution_id)
        if not student:
            await self.notif_repo.mark_result(log, NotificationStatus.SUPPRESSED)
            return

        student_name = f"{student.first_name} {student.last_name}"
        html = _build_html(student_name, delivery_date)
        try:
            self.email.send(log.email_to, log.subject, html)
        except Exception as exc:  # noqa: BLE001 — un fallo de correo no debe romper el job
            logger.exception("Fallo enviando correo de no reclamo PAE para %s", student_id)
            await self.notif_repo.mark_result(
                log, NotificationStatus.FAILED, error_message=str(exc)
            )
            return
        await self.notif_repo.mark_result(
            log, NotificationStatus.SENT, sent_at=datetime.now()
        )

    async def notify_late_claim_correction(
        self, institution_id: UUID, student_id: UUID, delivery_date: date
    ) -> None:
        """Red de seguridad: se dispara solo si `register_delivery` encontró una
        notificación PAE_NO_CLAIM ya enviada hoy para este estudiante (ej. un
        ADMIN adelantó `pae_delivery_end_time` a mitad del día). Con el bloqueo
        de entregas tardías en el service, este caso no debería ocurrir en
        operación normal."""
        student = await self.repo.get_active_student(student_id, institution_id)
        guardian = await self.repo.get_primary_guardian(student_id)
        if not student or not guardian:
            return

        student_name = f"{student.first_name} {student.last_name}"
        subject = f"Corrección: {student_name} sí reclamó el PAE hoy"
        html = _build_correction_html(student_name, delivery_date)

        notif_status = NotificationStatus.SENT
        error_message = None
        sent_at = datetime.now()
        try:
            self.email.send(guardian.email, subject, html)
        except Exception as exc:  # noqa: BLE001 — un fallo de correo no debe romper el job
            notif_status = NotificationStatus.FAILED
            error_message = str(exc)
            sent_at = None
            logger.exception(
                "Fallo enviando corrección de reclamo tardío PAE para %s", student_id
            )

        await self.notif_repo.create_log(
            institution_id=institution_id,
            type=NotificationType.PAE_LATE_CLAIM_CORRECTION,
            student_id=student.id,
            guardian_id=guardian.id,
            email_to=guardian.email,
            subject=subject,
            status=notif_status,
            error_message=error_message,
            sent_at=sent_at,
        )
