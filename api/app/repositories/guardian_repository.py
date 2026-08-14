from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guardian import Guardian


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

    async def create(self, guardian: Guardian) -> Guardian:
        self.session.add(guardian)
        await self.session.flush()
        await self.session.refresh(guardian)
        return guardian
