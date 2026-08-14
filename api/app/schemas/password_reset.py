from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(max_length=320)


class PasswordResetRequestResponse(BaseModel):
    """Respuesta deliberadamente ciega.

    Devuelve lo mismo exista o no la cuenta. Un "ese correo no está registrado"
    convierte el endpoint en un oráculo para averiguar qué docentes tienen
    cuenta en la institución.
    """

    sent: bool = True


class PasswordResetVerify(BaseModel):
    email: EmailStr = Field(max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetVerifyResponse(BaseModel):
    reset_token: UUID
    expires_in_seconds: int


class PasswordResetConfirm(BaseModel):
    reset_token: UUID
    # Mismo mínimo que `AdminUserCreate`, para no crear en la recuperación
    # contraseñas que el alta de usuarios rechazaría.
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResponse(BaseModel):
    changed: bool = True
