from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guardian import Guardian
from app.models.notification import NotificationLog


class GuardianRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_primary(self, student_id: UUID) -> Guardian | None:
        # guardians no tiene institution_id — el aislamiento viene del student_id,
        # que ya fue validado contra institution_id antes de llamar este método.
        result = await self.session.execute(
            select(Guardian).where(
                Guardian.student_id == student_id,
                Guardian.is_primary == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_student(self, student_id: UUID) -> list[Guardian]:
        # guardians no tiene institution_id — el aislamiento viene del student_id,
        # que ya fue validado contra institution_id antes de llamar este método.
        result = await self.session.execute(
            select(Guardian)
            .where(Guardian.student_id == student_id)
            .order_by(Guardian.is_primary.desc(), Guardian.created_at)
        )
        return list(result.scalars().all())

    async def create(self, guardian: Guardian) -> Guardian:
        self.session.add(guardian)
        await self.session.flush()
        await self.session.refresh(guardian)
        return guardian

    async def save(self, guardian: Guardian) -> Guardian:
        await self.session.flush()
        return guardian

    async def has_notifications(self, guardian_id: UUID) -> bool:
        # Se consulta ANTES de borrar (no se intenta el DELETE y se atrapa el
        # error): `notifications_log.guardian_id` es FK NOT NULL sin
        # ON DELETE, y un flush fallido deja la sesión async en estado
        # inválido para lo que quede de la transacción del request.
        result = await self.session.execute(
            select(NotificationLog.id).where(NotificationLog.guardian_id == guardian_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def delete(self, guardian: Guardian) -> None:
        await self.session.delete(guardian)
        await self.session.flush()
