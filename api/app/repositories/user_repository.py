from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        # Excepción justificada a la regla multi-tenant: este método solo se
        # usa en el dependency de autenticación, que es precisamente donde se
        # resuelve el institution_id del tenant activo.
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
