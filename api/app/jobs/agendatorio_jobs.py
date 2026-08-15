from uuid import UUID

from app.adapters.email.factory import get_email_adapter
from app.core.celery import celery_app
from app.jobs.runner import run_db_job
from app.services.discipline_notifier import DisciplineRecordNotifier


@celery_app.task
def notify_discipline_record(record_id: str, institution_id: str) -> None:
    run_db_job(
        lambda session: DisciplineRecordNotifier(session, get_email_adapter()).notify(
            UUID(record_id), UUID(institution_id)
        )
    )
