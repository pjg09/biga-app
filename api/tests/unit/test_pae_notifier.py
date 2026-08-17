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


async def test_encola_un_aviso_por_estudiante_como_pending():
    """Antes este test comprobaba que `notify_no_claims` **enviaba** los correos
    en un bucle. Ese diseño hacía que el proveedor rechazara casi todo el lote
    por límite de tasa, así que ahora encola una tarea por destinatario y deja la
    fila en PENDING; el envío y el SENT los hace `send_no_claim_email`."""
    institution_id = uuid4()
    s1, g1 = make_student("Ana", "Gómez"), make_guardian()
    s2, g2 = make_student("Luis", "Díaz"), make_guardian()

    with NotifierEnv() as env, patch("app.jobs.pae_jobs.send_pae_no_claim_email") as tarea:
        env.repo.count_deliveries_on.return_value = 10
        env.repo.get_no_claim_students_with_guardians.return_value = [(s1, g1), (s2, g2)]

        await env.notifier.notify_no_claims(institution_id, DELIVERY_DATE)

        # Nada se envía dentro del barrido: solo se prepara y se encola.
        env.email_adapter.send.assert_not_called()
        assert tarea.apply_async.call_count == 2
        assert env.notification_repo.create_log.call_count == 2

        first = env.notification_repo.create_log.call_args_list[0].kwargs
        assert first["status"] == NotificationStatus.PENDING
        assert first["type"] == NotificationType.PAE_NO_CLAIM
        assert first["institution_id"] == institution_id
        assert first["student_id"] == s1.id
        assert first["guardian_id"] == g1.id
        assert first["email_to"] == g1.email

        # Escalonados: el segundo sale después del primero.
        esperas = [c.kwargs["countdown"] for c in tarea.apply_async.call_args_list]
        assert esperas[1] > esperas[0]


async def test_el_fallo_de_un_correo_no_afecta_a_los_demas():
    """Con el bucle anterior, un fallo se manejaba dentro del mismo job y el
    lote seguía. Ahora la garantía es más fuerte y no depende de un `try`: cada
    correo es su propia tarea de Celery, así que el que falla se registra FAILED
    por su cuenta y no toca a los otros, que ya están encolados aparte."""
    s1, g1 = make_student("Ana", "Gómez"), make_guardian()
    s2, g2 = make_student("Luis", "Díaz"), make_guardian()

    with NotifierEnv() as env, patch("app.jobs.pae_jobs.send_pae_no_claim_email") as tarea:
        env.repo.count_deliveries_on.return_value = 10
        env.repo.get_no_claim_students_with_guardians.return_value = [(s1, g1), (s2, g2)]
        # Cada inserción devuelve una fila distinta, como en la BD real: el
        # AsyncMock por defecto devolvería siempre el mismo objeto y el test no
        # podría distinguir una notificación de otra.
        env.notification_repo.create_log.side_effect = lambda **kw: MagicMock(id=uuid4())

        await env.notifier.notify_no_claims(uuid4(), DELIVERY_DATE)

        assert tarea.apply_async.call_count == 2
        # Los ids de notificación encolados son distintos: cada tarea cierra su
        # propia fila, así que ninguna puede pisar el resultado de otra.
        ids = [c.args[0][0] for c in tarea.apply_async.call_args_list]
        assert len(set(ids)) == 2


async def test_late_claim_correction_sends_and_logs():
    institution_id = uuid4()
    student = make_student("Ana", "Gómez")
    guardian = make_guardian()

    with NotifierEnv() as env:
        env.repo.get_active_student.return_value = student
        env.repo.get_primary_guardian.return_value = guardian

        await env.notifier.notify_late_claim_correction(institution_id, student.id, DELIVERY_DATE)

        env.email_adapter.send.assert_called_once()
        assert env.notification_repo.create_log.call_count == 1
        logged = env.notification_repo.create_log.call_args.kwargs
        assert logged["type"] == NotificationType.PAE_LATE_CLAIM_CORRECTION
        assert logged["status"] == NotificationStatus.SENT
        assert logged["student_id"] == student.id
        assert logged["guardian_id"] == guardian.id


async def test_late_claim_correction_skips_without_guardian():
    with NotifierEnv() as env:
        env.repo.get_active_student.return_value = make_student()
        env.repo.get_primary_guardian.return_value = None

        await env.notifier.notify_late_claim_correction(uuid4(), uuid4(), DELIVERY_DATE)

        env.email_adapter.send.assert_not_called()
        env.notification_repo.create_log.assert_not_called()


async def test_late_claim_correction_email_failure_marks_failed():
    institution_id = uuid4()
    student = make_student("Ana", "Gómez")
    guardian = make_guardian()

    with NotifierEnv() as env:
        env.repo.get_active_student.return_value = student
        env.repo.get_primary_guardian.return_value = guardian
        env.email_adapter.send.side_effect = RuntimeError("resend down")

        await env.notifier.notify_late_claim_correction(institution_id, student.id, DELIVERY_DATE)

        logged = env.notification_repo.create_log.call_args.kwargs
        assert logged["status"] == NotificationStatus.FAILED
        assert logged["error_message"] == "resend down"
        assert logged["sent_at"] is None
