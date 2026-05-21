from app.core.celery import celery_app


@celery_app.task
def notify_discipline_record(record_id: str) -> None:
    pass
