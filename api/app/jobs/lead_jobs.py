from uuid import UUID

from app.adapters.email.resend import ResendEmailAdapter
from app.core.celery import celery_app
from app.jobs.runner import run_db_job
from app.services.lead_notifier import LeadNotifier


@celery_app.task
def notify_demo_lead(lead_id: str) -> None:
    demo_lead_id = UUID(lead_id)
    run_db_job(lambda session: LeadNotifier(session, ResendEmailAdapter()).notify(demo_lead_id))
