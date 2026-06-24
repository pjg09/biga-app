import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.base import EmailAdapter
from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord
from app.models.enums import NotificationStatus, NotificationType
from app.models.student import Student
from app.repositories.agendatorio_repository import AgendatorioRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.student_repository import StudentRepository

logger = logging.getLogger(__name__)


def _build_html(student: Student, record: DisciplineRecord, articles: list[ConvivenciaArticle]) -> str:
    articles_html = "".join(f"<li>{article.code} — {article.title}</li>" for article in articles)
    return (
        f"<p>Se ha registrado una anotación en el manual de convivencia para "
        f"<strong>{student.first_name} {student.last_name}</strong> "
        f"con fecha {record.date.strftime('%d/%m/%Y')}.</p>"
        f"<p><strong>Artículos infringidos:</strong></p>"
        f"<ul>{articles_html}</ul>"
        f"<p><strong>Observaciones:</strong> {record.observations}</p>"
    )


class DisciplineRecordNotifier:
    """Lado de job: notifica al acudiente un registro disciplinario nuevo."""

    def __init__(self, session: AsyncSession, email: EmailAdapter):
        self.session = session
        self.repo = AgendatorioRepository(session)
        self.student_repo = StudentRepository(session)
        self.guardian_repo = GuardianRepository(session)
        self.notif_repo = NotificationRepository(session)
        self.email = email

    async def notify(self, record_id: UUID, institution_id: UUID) -> None:
        record, articles = await self.repo.get_record(record_id, institution_id)
        if record is None:
            logger.error(
                "notify_discipline_record: registro %s no encontrado en institución %s",
                record_id,
                institution_id,
            )
            return

        student = await self.student_repo.get_by_id(record.student_id, institution_id)
        guardian = await self.guardian_repo.get_primary(record.student_id)
        if student is None or guardian is None:
            logger.error(
                "notify_discipline_record: falta estudiante o acudiente primario para el registro %s",
                record_id,
            )
            return

        subject = f"Registro disciplinario — {student.first_name} {student.last_name}"
        html = _build_html(student, record, articles)

        notif_status = NotificationStatus.SENT
        error_message = None
        sent_at: datetime | None = datetime.now()
        try:
            self.email.send(guardian.email, subject, html)
        except Exception as exc:  # noqa: BLE001 — fallo de correo no debe romper el job
            notif_status = NotificationStatus.FAILED
            error_message = str(exc)
            sent_at = None
            logger.exception(
                "notify_discipline_record: error enviando email para el registro %s", record_id
            )

        await self.notif_repo.create_log(
            institution_id=institution_id,
            type=NotificationType.DISCIPLINE_RECORD,
            student_id=student.id,
            guardian_id=guardian.id,
            email_to=guardian.email,
            subject=subject,
            status=notif_status,
            error_message=error_message,
            sent_at=sent_at,
        )
