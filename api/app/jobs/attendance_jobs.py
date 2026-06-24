from uuid import UUID

from app.adapters.email.resend import ResendEmailAdapter
from app.core.celery import celery_app
from app.jobs.runner import run_db_job
from app.services.attendance_notifier import AttendanceNotifier


@celery_app.task
def notify_absence_first_hour(attendance_record_id: str) -> None:
    record_id = UUID(attendance_record_id)
    run_db_job(
        lambda session: AttendanceNotifier(session, ResendEmailAdapter()).notify_absence(record_id)
    )
