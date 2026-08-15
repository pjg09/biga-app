from uuid import UUID

from app.adapters.email.factory import get_email_adapter
from app.core.celery import celery_app
from app.jobs.runner import run_db_job
from app.services.departure_notifier import DepartureNotifier


@celery_app.task
def notify_early_departure(early_departure_id: str) -> None:
    departure_id = UUID(early_departure_id)
    run_db_job(
        lambda session: DepartureNotifier(session, get_email_adapter()).notify(departure_id)
    )
