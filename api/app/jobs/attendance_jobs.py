from app.core.celery import celery_app


@celery_app.task
def notify_absence_first_hour(attendance_record_id: str) -> None:
    pass
