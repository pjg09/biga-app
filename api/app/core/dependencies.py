from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(token)
    user = await UserRepository(db).get_by_id(UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo")
    return user


# El operador PAE es un docente con funciones extra del PAE: ambos roles pueden
# usar las funciones de aula (asistencia, salidas, horario, convivencia).
def require_staff(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.TEACHER, UserRole.PAE_OPERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo personal docente puede acceder a este recurso",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden acceder a este recurso",
        )
    return current_user


def get_storage_adapter() -> S3StorageAdapter:
    return S3StorageAdapter()
