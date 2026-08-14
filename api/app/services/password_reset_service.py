import logging
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import generate_otp_code, hash_password, verify_password
from app.jobs.auth_jobs import notify_password_reset_code
from app.models.password_reset import PasswordResetOTP
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.password_reset import (
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    PasswordResetVerify,
    PasswordResetVerifyResponse,
)

logger = logging.getLogger(__name__)

# Un único mensaje para "código incorrecto", "código caducado", "ya usado",
# "demasiados intentos" y "ese correo no tiene código". Distinguirlos le diría a
# un atacante si va por buen camino.
INVALID_CODE_DETAIL = "Código inválido o expirado. Solicita uno nuevo."


class PasswordResetService:
    def __init__(self, repo: PasswordResetRepository, user_repo: UserRepository):
        self.repo = repo
        self.user_repo = user_repo

    async def request_code(self, data: PasswordResetRequest) -> PasswordResetRequestResponse:
        email = str(data.email).strip().lower()
        user = await self.user_repo.get_by_email(email)
        now = datetime.now()

        # Cuenta inexistente o desactivada: se responde igual y no se hace nada.
        # No es un fallo silencioso, es el comportamiento correcto — ver el
        # docstring de PasswordResetRequestResponse.
        if user is None or not user.is_active:
            logger.info("Código de recuperación pedido para un correo sin cuenta activa")
            return PasswordResetRequestResponse()

        await self.repo.expire_active_for_user(user.id, now)

        code = generate_otp_code()
        otp = PasswordResetOTP(
            id=uuid4(),
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=now + timedelta(minutes=settings.password_reset_otp_ttl_minutes),
        )
        await self.repo.create(otp)

        # countdown corto: el job no lee la BD, pero si el request acabara
        # revirtiendo, el correo habría anunciado un código que no existe.
        #
        # `argsrepr` sustituye lo que Celery imprime en los logs. Sin él, el
        # volcado de un task fallido escupe el OTP en claro en los logs del
        # worker, que se guardan y rotan en sitios donde el código no pinta nada.
        notify_password_reset_code.apply_async(
            (email, user.first_name, code, settings.password_reset_otp_ttl_minutes),
            countdown=2,
            argsrepr="('<correo>', '<nombre>', '<codigo oculto>', ttl)",
        )
        return PasswordResetRequestResponse()

    async def verify_code(self, data: PasswordResetVerify) -> PasswordResetVerifyResponse | None:
        """Devuelve `None` si el código no es válido; **no lanza**.

        `get_db()` hace rollback ante excepción. Si esto lanzara `HTTPException`
        en el camino de fallo, el `attempts += 1` se revertiría con ella y el
        contador de intentos jamás subiría: la protección contra fuerza bruta
        quedaría de adorno. El router traduce el `None` a un 400 devolviendo una
        respuesta, que sí deja cerrar la transacción y persistir el intento.
        """
        email = str(data.email).strip().lower()
        user = await self.user_repo.get_by_email(email)
        now = datetime.now()

        if user is None or not user.is_active:
            return None

        otp = await self.repo.get_active_for_user(user.id, now)
        if otp is None:
            return None

        if otp.attempts >= settings.password_reset_max_attempts:
            # Se quema el código: quien fuerza no puede seguir probando ni
            # aunque el TTL siga vivo.
            otp.expires_at = now
            return None

        if not verify_password(data.code, otp.code_hash):
            otp.attempts += 1
            return None

        otp.consumed_at = now
        otp.reset_token = uuid4()
        otp.reset_token_expires_at = now + timedelta(
            minutes=settings.password_reset_token_ttl_minutes
        )
        return PasswordResetVerifyResponse(
            reset_token=otp.reset_token,
            expires_in_seconds=settings.password_reset_token_ttl_minutes * 60,
        )

    async def confirm(self, data: PasswordResetConfirm) -> PasswordResetConfirmResponse:
        now = datetime.now()
        otp = await self.repo.get_by_reset_token(data.reset_token)

        invalid = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La sesión de recuperación expiró. Vuelve a solicitar un código.",
        )
        if otp is None or otp.reset_token_expires_at is None:
            raise invalid
        if otp.reset_token_used_at is not None or otp.reset_token_expires_at <= now:
            raise invalid

        user = await self.user_repo.get_by_id(otp.user_id)
        if user is None or not user.is_active:
            raise invalid

        user.hashed_password = hash_password(data.new_password)
        otp.reset_token_used_at = now
        # Cualquier otro código o token del usuario muere aquí: si alguien más
        # había pedido un código para esta cuenta, deja de servir.
        await self.repo.invalidate_all_for_user(user.id, now)

        logger.info("Contraseña restablecida para el usuario %s", user.id)
        return PasswordResetConfirmResponse()
