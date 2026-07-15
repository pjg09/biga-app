from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.enums import NotificationStatus, NotificationType
from app.models.guardian import Guardian
from app.models.student import Student
from app.services.pae_notifier import PAENotifier

DELIVERY_DATE = date(2026, 6, 26)


def make_student(first="Juan", last="Pérez") -> Student:
    student = MagicMock(spec=Student)
    student.id = uuid4()
    student.first_name = first
    student.last_name = last
    return student


def make_guardian() -> Guardian:
    guardian = MagicMock(spec=Guardian)
    guardian.id = uuid4()
    guardian.email = "acudiente@example.com"
    return guardian


class NotifierEnv:
    """Parchea los repositorios de PAENotifier para probar `notify_no_claims`
    sin BD ni envío real de correo."""

    def __init__(self):
        self.session = MagicMock()
        self.repo = AsyncMock()
        self.notification_repo = AsyncMock()
        self.email_adapter = MagicMock()

        self._patches = [
            patch("app.services.pae_notifier.PAERepository", return_value=self.repo),
            patch(
                "app.services.pae_notifier.NotificationRepository",
                return_value=self.notification_repo,
            ),
        ]

    def __enter__(self) -> "NotifierEnv":
        for p in self._patches:
            p.start()
        self.notifier = PAENotifier(self.session, self.email_adapter)
        return self

    def __exit__(self, *exc_info) -> None:
        for p in reversed(self._patches):
            p.stop()


async def test_no_deliveries_that_day_does_not_notify():
    with NotifierEnv() as env:
        env.repo.count_deliveries_on.return_value = 0

        await env.notifier.notify_no_claims(uuid4(), DELIVERY_DATE)

        env.repo.get_no_claim_students_with_guardians.assert_not_called()
        env.email_adapter.send.assert_not_called()
        env.notification_repo.create_log.assert_not_called()


async def test_no_candidates_does_not_notify():
    with NotifierEnv() as env:
        env.repo.count_deliveries_on.return_value = 5
        env.repo.get_no_claim_students_with_guardians.return_value = []

        await env.notifier.notify_no_claims(uuid4(), DELIVERY_DATE)

        env.email_adapter.send.assert_not_called()
        env.notification_repo.create_log.assert_not_called()


async def test_notifies_each_no_claim_student_and_logs_sent():
    institution_id = uuid4()
    s1, g1 = make_student("Ana", "Gómez"), make_guardian()
    s2, g2 = make_student("Luis", "Díaz"), make_guardian()

    with NotifierEnv() as env:
        env.repo.count_deliveries_on.return_value = 10
        env.repo.get_no_claim_students_with_guardians.return_value = [(s1, g1), (s2, g2)]

        await env.notifier.notify_no_claims(institution_id, DELIVERY_DATE)

        assert env.email_adapter.send.call_count == 2
        assert env.notification_repo.create_log.call_count == 2

        first = env.notification_repo.create_log.call_args_list[0].kwargs
        assert first["status"] == NotificationStatus.SENT
        assert first["type"] == NotificationType.PAE_NO_CLAIM
        assert first["institution_id"] == institution_id
        assert first["student_id"] == s1.id
        assert first["guardian_id"] == g1.id
        assert first["email_to"] == g1.email
        assert first["error_message"] is None
        assert first["sent_at"] is not None


async def test_email_failure_marks_failed_and_continues_next_student():
    s1, g1 = make_student("Ana", "Gómez"), make_guardian()
    s2, g2 = make_student("Luis", "Díaz"), make_guardian()

    with NotifierEnv() as env:
        env.repo.count_deliveries_on.return_value = 10
        env.repo.get_no_claim_students_with_guardians.return_value = [(s1, g1), (s2, g2)]
        # El primer envío falla; el lote no debe romperse.
        env.email_adapter.send.side_effect = [RuntimeError("resend down"), None]

        await env.notifier.notify_no_claims(uuid4(), DELIVERY_DATE)

        assert env.notification_repo.create_log.call_count == 2
        failed = env.notification_repo.create_log.call_args_list[0].kwargs
        assert failed["status"] == NotificationStatus.FAILED
        assert failed["error_message"] == "resend down"
        assert failed["sent_at"] is None

        ok = env.notification_repo.create_log.call_args_list[1].kwargs
        assert ok["status"] == NotificationStatus.SENT
