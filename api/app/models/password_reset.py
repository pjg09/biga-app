from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PasswordResetOTP(Base):
    """Código de un solo uso para recuperar la contraseña.

    No lleva `institution_id`: el flujo es previo a la autenticación y el
    usuario se resuelve por correo, que es único en toda la tabla `users`. El
    tenant se deriva del propio `user_id`, no de la request.

    El código **nunca se guarda en claro** (`code_hash`, bcrypt). Un código de 6
    dígitos son solo un millón de combinaciones: con un hash rápido, una fuga de
    la BD se revierte en segundos.
    """

    __tablename__ = "password_reset_otps"
    __table_args__ = (
        Index("idx_password_reset_user", "user_id", "created_at"),
        Index("idx_password_reset_token", "reset_token"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    # Se sella al validar el código: a partir de ahí el OTP ya no sirve.
    consumed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Prueba de que el OTP fue validado. Sin esto, el paso de cambio de
    # contraseña tendría que fiarse de que el cliente dice haber pasado el OTP.
    reset_token: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, unique=True
    )
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    reset_token_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
