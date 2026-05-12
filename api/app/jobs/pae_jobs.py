from app.core.celery import celery_app


@celery_app.task
def notify_pae_no_claim(institution_id: str, delivery_date: str) -> None:
    pass
