from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord
from app.models.enums import NotificationStatus
from app.models.guardian import Guardian
from app.models.student import Student
from app.services.discipline_notifier import DisciplineRecordNotifier


def make_record() -> DisciplineRecord:
    record = MagicMock(spec=DisciplineRecord)
    record.id = uuid4()
    record.student_id = uuid4()
    record.date = date(2026, 5, 21)
    record.observations = "Uso del celular durante evaluación"
    return record


def make_article() -> ConvivenciaArticle:
    article = MagicMock(spec=ConvivenciaArticle)
    article.code = "Art.15"
    article.title = "Uso inadecuado del celular"
    return article


def make_student() -> Student:
    student = MagicMock(spec=Student)
    student.id = uuid4()
    student.first_name = "Juan"
    student.last_name = "Pérez"
    return student


def make_guardian() -> Guardian:
    guardian = MagicMock(spec=Guardian)
    guardian.id = uuid4()
    guardian.email = "acudiente@example.com"
    return guardian


class NotifierEnv:
    """Parchea los repositorios de DisciplineRecordNotifier para probar `notify`
    sin BD ni envío real de correo."""

    def __init__(self):
        self.session = MagicMock()
        self.repo = AsyncMock()
        self.student_repo = AsyncMock()
        self.guardian_repo = AsyncMock()
        self.notification_repo = AsyncMock()
        self.email_adapter = MagicMock()

        self._patches = [
            patch("app.services.discipline_notifier.AgendatorioRepository", return_value=self.repo),
            patch("app.services.discipline_notifier.StudentRepository", return_value=self.student_repo),
            patch("app.services.discipline_notifier.GuardianRepository", return_value=self.guardian_repo),
            patch(
                "app.services.discipline_notifier.NotificationRepository",
                return_value=self.notification_repo,
            ),
        ]

    def __enter__(self) -> "NotifierEnv":
        for p in self._patches:
            p.start()
        self.notifier = DisciplineRecordNotifier(self.session, self.email_adapter)
        return self

    def __exit__(self, *exc_info) -> None:
        for p in reversed(self._patches):
            p.stop()


async def test_notify_discipline_record_returns_early_if_record_not_found():
    with NotifierEnv() as env:
        env.repo.get_record.return_value = (None, [])

        await env.notifier.notify(uuid4(), uuid4())

        env.notification_repo.create_log.assert_not_called()
        env.email_adapter.send.assert_not_called()


async def test_notify_discipline_record_returns_early_without_primary_guardian():
    record = make_record()
    with NotifierEnv() as env:
        env.repo.get_record.return_value = (record, [make_article()])
        env.student_repo.get_by_id.return_value = make_student()
        env.guardian_repo.get_primary.return_value = None

        await env.notifier.notify(record.id, uuid4())

        env.notification_repo.create_log.assert_not_called()
        env.email_adapter.send.assert_not_called()


async def test_notify_discipline_record_success_marks_sent():
    record = make_record()
    student = make_student()
    guardian = make_guardian()
    institution_id = uuid4()

    with NotifierEnv() as env:
        env.repo.get_record.return_value = (record, [make_article()])
        env.student_repo.get_by_id.return_value = student
        env.guardian_repo.get_primary.return_value = guardian

        await env.notifier.notify(record.id, institution_id)

        env.email_adapter.send.assert_called_once()
        assert env.email_adapter.send.call_args.args[0] == guardian.email

        create_kwargs = env.notification_repo.create_log.call_args.kwargs
        assert create_kwargs["status"] == NotificationStatus.SENT
        assert create_kwargs["error_message"] is None
        assert create_kwargs["sent_at"] is not None
        assert create_kwargs["institution_id"] == institution_id
        assert create_kwargs["student_id"] == student.id
        assert create_kwargs["guardian_id"] == guardian.id
        assert create_kwargs["email_to"] == guardian.email


async def test_notify_discipline_record_email_failure_marks_failed_without_raising():
    record = make_record()
    student = make_student()
    guardian = make_guardian()

    with NotifierEnv() as env:
        env.repo.get_record.return_value = (record, [make_article()])
        env.student_repo.get_by_id.return_value = student
        env.guardian_repo.get_primary.return_value = guardian
        env.email_adapter.send.side_effect = RuntimeError("resend down")

        await env.notifier.notify(record.id, uuid4())

        create_kwargs = env.notification_repo.create_log.call_args.kwargs
        assert create_kwargs["status"] == NotificationStatus.FAILED
        assert create_kwargs["error_message"] == "resend down"
        assert create_kwargs["sent_at"] is None
