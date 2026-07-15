from celery import Celery
from celery.schedules import crontab

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

# El barrido corre cada 15 min: dentro de esa ventana tras la hora de cierre del
# PAE de cada institución se disparan las notificaciones de no reclamo. No se
# programa por institución (Celery beat es estático); el barrido lee la hora de
# cierre de cada una desde la BD.
celery_app.conf.beat_schedule = {
    "sweep-pae-no-claim": {
        "task": "app.jobs.pae_jobs.sweep_pae_no_claim",
        "schedule": crontab(minute="*/15"),
    },
}
