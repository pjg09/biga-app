from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email.resend import ResendEmailAdapter
from app.core.celery import celery_app
from app.jobs.runner import run_db_job
from app.repositories.pae_repository import PAERepository
from app.services.pae_notifier import PAENotifier

BOGOTA = ZoneInfo("America/Bogota")


async def _dispatch_no_claim(session: AsyncSession, now: datetime) -> None:
    repo = PAERepository(session)
    institution_ids = await repo.get_institution_ids_past_pae_end(now.time())
    today = now.date().isoformat()
    for institution_id in institution_ids:
        # Fan-out per-institución: cada job lleva institution_id explícito (regla
        # multi-tenant) y aísla el fallo de una institución de las demás.
        notify_pae_no_claim.delay(str(institution_id), today)


@celery_app.task
def sweep_pae_no_claim() -> None:
    """Barrido programado (Celery beat). Encola la notificación de no reclamo para
    cada institución cuya hora de cierre del PAE ya pasó hoy. Idempotente: el
    PAENotifier omite a los estudiantes ya notificados, así que correr varias
    veces en la tarde no genera correos duplicados."""
    now = datetime.now(BOGOTA)
    run_db_job(lambda session: _dispatch_no_claim(session, now))


@celery_app.task
def notify_pae_no_claim(institution_id: str, delivery_date: str) -> None:
    inst = UUID(institution_id)
    day = date.fromisoformat(delivery_date)
    run_db_job(
        lambda session: PAENotifier(session, ResendEmailAdapter()).notify_no_claims(inst, day)
    )


@celery_app.task
def notify_pae_late_claim_correction(institution_id: str, student_id: str, delivery_date: str) -> None:
    inst = UUID(institution_id)
    student = UUID(student_id)
    day = date.fromisoformat(delivery_date)
    run_db_job(
        lambda session: PAENotifier(session, ResendEmailAdapter()).notify_late_claim_correction(
            inst, student, day
        )
    )
