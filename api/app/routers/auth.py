from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.models.user import User
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserResponse
from app.schemas.password_reset import (
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    PasswordResetVerify,
    PasswordResetVerifyResponse,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService, INVALID_CODE_DETAIL

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))


def get_password_reset_service(db: AsyncSession = Depends(get_db)) -> PasswordResetService:
    return PasswordResetService(PasswordResetRepository(db), UserRepository(db))


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    token = await service.login(email=form.username, password=form.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Recuperación de contraseña (endpoints públicos, sin JWT) ---
#
# Los tres son anónimos por definición: quien no puede entrar tampoco tiene
# token. La autorización la dan, en orden, el correo (paso 1), el código OTP
# (paso 2) y el `reset_token` emitido por el servidor (paso 3).

@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    service: PasswordResetService = Depends(get_password_reset_service),
):
    await enforce_rate_limit(
        request,
        bucket="pwd-reset-request",
        max_hits=settings.password_reset_rate_limit_max,
        window_seconds=settings.password_reset_rate_limit_window_seconds,
    )
    return await service.request_code(body)


@router.post("/password-reset/verify", response_model=PasswordResetVerifyResponse)
async def verify_password_reset(
    request: Request,
    body: PasswordResetVerify,
    service: PasswordResetService = Depends(get_password_reset_service),
):
    await enforce_rate_limit(
        request,
        bucket="pwd-reset-verify",
        max_hits=settings.password_reset_verify_rate_limit_max,
        window_seconds=settings.password_reset_rate_limit_window_seconds,
    )
    result = await service.verify_code(body)
    if result is None:
        # El 400 se **devuelve**, no se lanza: una HTTPException haría rollback
        # en `get_db()` y se perdería el incremento de `attempts` que acaba de
        # registrar el intento fallido.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": INVALID_CODE_DETAIL}
        )
    return result


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    service: PasswordResetService = Depends(get_password_reset_service),
):
    return await service.confirm(body)
