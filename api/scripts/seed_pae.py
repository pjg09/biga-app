"""Datos de prueba del PAE: inscribe a los estudiantes demo y registra entregas
con la cadena de doble hash válida (enrollment_hash + delivery_hash).

No se puede sembrar por SQL plano porque los hashes dependen de PAE_SIGNING_SECRET
y del timestamp. Este script corre dentro del contenedor, donde está la clave:

    docker compose exec -T api python -m scripts.seed_pae

Es idempotente: omite inscripciones y entregas que ya existan.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import compute_delivery_hash, compute_enrollment_hash
from app.models.enums import PAEIdentificationMethod
from app.models.pae import PAEDelivery, PAEEnrollment

INSTITUTION_ID = UUID("a0000000-0000-0000-0000-000000000001")
PAE_USER_ID = UUID("b0000000-0000-0000-0000-000000000002")  # pae@iedemo.edu.co
STUDENT_IDS = [
    UUID("c0000000-0000-0000-0000-000000000001"),  # Mariana
    UUID("c0000000-0000-0000-0000-000000000002"),  # Santiago
    UUID("c0000000-0000-0000-0000-000000000003"),  # Valentina
    UUID("c0000000-0000-0000-0000-000000000004"),  # Mateo
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def seed():
    async with AsyncSessionLocal() as db:
        year = date.today().year
        enrollments: dict[UUID, PAEEnrollment] = {}

        # 1. Inscribir a los 4 estudiantes (capa 1 del hash).
        for sid in STUDENT_IDS:
            existing = (
                await db.execute(
                    select(PAEEnrollment).where(
                        PAEEnrollment.student_id == sid,
                        PAEEnrollment.academic_year == year,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                enrollments[sid] = existing
                continue

            enrolled_at = _now()
            enrollment = PAEEnrollment(
                id=uuid4(),
                student_id=sid,
                institution_id=INSTITUTION_ID,
                academic_year=year,
                is_active=True,
                enrolled_at=enrolled_at,
                enrollment_hash=compute_enrollment_hash(sid, INSTITUTION_ID, year, enrolled_at),
            )
            db.add(enrollment)
            enrollments[sid] = enrollment
        await db.flush()

        # 2. Entregas de la semana (capa 2 encadena la capa 1).
        #    Hoy se entrega solo a 2 de 4 (deja 2 pendientes visibles en el
        #    listado del día); los días anteriores de la semana, a 3 de 4.
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        delivered = 0
        for offset in range(today.weekday() + 1):
            day = week_start + timedelta(days=offset)
            day_students = STUDENT_IDS[:2] if day == today else STUDENT_IDS[:3]
            for sid in day_students:
                exists = (
                    await db.execute(
                        select(PAEDelivery).where(
                            PAEDelivery.student_id == sid,
                            PAEDelivery.delivery_date == day,
                        )
                    )
                ).scalar_one_or_none()
                if exists:
                    continue

                created_at = datetime.combine(day, datetime.min.time())
                enrollment_hash = enrollments[sid].enrollment_hash
                delivery = PAEDelivery(
                    id=uuid4(),
                    student_id=sid,
                    institution_id=INSTITUTION_ID,
                    delivered_by_user_id=PAE_USER_ID,
                    delivery_date=day,
                    identification_method=PAEIdentificationMethod.DOCUMENT,
                    delivery_hash=compute_delivery_hash(
                        student_id=sid,
                        delivery_date=day,
                        delivered_by_user_id=PAE_USER_ID,
                        created_at=created_at,
                        enrollment_hash=enrollment_hash,
                    ),
                    created_at=created_at,
                )
                db.add(delivery)
                delivered += 1

        await db.commit()
        print(f"Inscritos: {len(enrollments)} · entregas nuevas: {delivered}")


asyncio.run(seed())
