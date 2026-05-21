"""Datos de prueba para testear el módulo agendatorio. Ejecutar desde la raíz:
    docker compose exec api python scripts/seed_agendatorio.py
"""
import asyncio
from datetime import date
from uuid import uuid4

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.enums import GuardianRelationship
from app.models.guardian import Guardian
from app.models.institution import Institution
from app.models.student import Student


async def seed():
    async with AsyncSessionLocal() as db:
        inst = (await db.execute(select(Institution))).scalar_one()

        student = Student(
            id=uuid4(),
            institution_id=inst.id,
            document_number="87654321",
            first_name="Laura",
            last_name="Suarez",
            birth_date=date(2006, 11, 9),
            is_active=True,
        )
        db.add(student)
        await db.flush()

        guardian = Guardian(
            id=uuid4(),
            student_id=student.id,
            full_name="Ana Lozano",
            relationship=GuardianRelationship.MADRE,
            email="ana@example.com",
            is_primary=True,
        )
        db.add(guardian)
        await db.commit()

        print(f"student_id={student.id}")
        print(f"institution_id={inst.id}")


asyncio.run(seed())
