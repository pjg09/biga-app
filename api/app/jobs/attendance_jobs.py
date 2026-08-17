from uuid import UUID

from app.adapters.email.factory import get_email_adapter
from app.core.celery import celery_app
from app.core.config import settings
from app.jobs.runner import run_db_job
from app.services.attendance_notifier import AttendanceNotifier


@celery_app.task(rate_limit=settings.email_rate_limit)
def notify_absence_first_hour(attendance_record_id: str) -> None:
    record_id = UUID(attendance_record_id)
    run_db_job(
        lambda session: AttendanceNotifier(session, get_email_adapter()).notify_absence(record_id)
    )
