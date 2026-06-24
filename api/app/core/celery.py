from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "biga",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.jobs.pae_jobs",
        "app.jobs.attendance_jobs",
        "app.jobs.departure_jobs",
        "app.jobs.agendatorio_jobs",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
)
