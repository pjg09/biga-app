from fastapi import HTTPException, status

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    # Hash ficticio para que bcrypt corra siempre, independientemente de si el
    # usuario existe. Evita enumeración por timing (email inexistente ~1ms vs
    # contraseña incorrecta ~200ms).
    _DUMMY_HASH = "$2b$12$bk/XrYi7ky2L.1LE1mY4j.3GO8AQjthElKEFblkeIQtD.EZELzIwu"

    async def login(self, email: str, password: str) -> str:
        user = await self.repo.get_by_email(email)
        hash_to_check = user.hashed_password if user else self._DUMMY_HASH
        password_ok = verify_password(password, hash_to_check)

        if not user or not password_ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo",
            )
        return create_access_token(subject=str(user.id))
