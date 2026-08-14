from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetOTP


class PasswordResetRepository:
    """Acceso a `password_reset_otps`.

    Sin parámetro `institution_id`: el flujo es previo a la autenticación y no
    hay tenant en la request. El aislamiento lo da el `user_id`, que sale de
    buscar el correo en `users`, nunca de la petición.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, otp: PasswordResetOTP) -> PasswordResetOTP:
        self.session.add(otp)
        await self.session.flush()
        await self.session.refresh(otp)
        return otp

    async def expire_active_for_user(self, user_id: UUID, now: datetime) -> None:
        """Caduca los OTP vivos del usuario: solo el último pedido vale."""
        await self.session.execute(
            update(PasswordResetOTP)
            .where(
                PasswordResetOTP.user_id == user_id,
                PasswordResetOTP.consumed_at.is_(None),
                PasswordResetOTP.expires_at > now,
            )
            .values(expires_at=now)
        )

    async def get_active_for_user(self, user_id: UUID, now: datetime) -> PasswordResetOTP | None:
        """OTP más reciente aún válido: sin consumir y sin caducar."""
        result = await self.session.execute(
            select(PasswordResetOTP)
            .where(
                PasswordResetOTP.user_id == user_id,
                PasswordResetOTP.consumed_at.is_(None),
                PasswordResetOTP.expires_at > now,
            )
            .order_by(PasswordResetOTP.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: UUID) -> PasswordResetOTP | None:
        result = await self.session.execute(
            select(PasswordResetOTP).where(PasswordResetOTP.reset_token == token)
        )
        return result.scalar_one_or_none()

    async def invalidate_all_for_user(self, user_id: UUID, now: datetime) -> None:
        """Tras cambiar la contraseña no debe quedar ningún código ni token vivo."""
        await self.session.execute(
            update(PasswordResetOTP)
            .where(PasswordResetOTP.user_id == user_id)
            .values(expires_at=now, reset_token_expires_at=now)
        )
