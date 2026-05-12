from app.core.celery import celery_app


@celery_app.task
def notify_early_departure(early_departure_id: str) -> None:
    pass
