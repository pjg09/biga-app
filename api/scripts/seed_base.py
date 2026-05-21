"""Crea institución y usuario de prueba. Ejecutar desde la raíz:
    docker compose exec api python -m scripts.seed_base
"""
import asyncio
from datetime import time
from uuid import uuid4

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User


async def seed():
    async with AsyncSessionLocal() as db:
        inst = Institution(
            id=uuid4(),
            name="Colegio Demo",
            nit="900000001",
            address="Calle 1",
            city="Bogota",
            pae_delivery_end_time=time(12, 0),
        )
        db.add(inst)
        await db.flush()

        user = User(
            id=uuid4(),
            institution_id=inst.id,
            document_number="12345678",
            first_name="Pedro",
            last_name="Demo",
            email="demo@biga.app",
            hashed_password=hash_password("Test1234!"),
            role=UserRole.TEACHER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        print(f"institution_id={inst.id}")
        print(f"user_id={user.id}")


asyncio.run(seed())
