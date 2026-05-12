from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.models.user import User
from app.core.security import hash_password
from app.services.auth_service import AuthService


def make_user(*, is_active: bool = True, password: str = "Test1234!") -> User:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.institution_id = uuid4()
    user.email = "docente@biga.app"
    user.hashed_password = hash_password(password)
    user.role = UserRole.TEACHER
    user.is_active = is_active
    return user


def make_service(user: User | None) -> AuthService:
    repo = AsyncMock()
    repo.get_by_email.return_value = user
    return AuthService(repo)


async def test_login_returns_token():
    user = make_user()
    service = make_service(user)
    token = await service.login("docente@biga.app", "Test1234!")
    assert isinstance(token, str)
    assert len(token) > 20


async def test_login_wrong_password_raises_401():
    user = make_user()
    service = make_service(user)
    with pytest.raises(HTTPException) as exc_info:
        await service.login("docente@biga.app", "incorrect")
    assert exc_info.value.status_code == 401


async def test_login_unknown_email_raises_401():
    service = make_service(user=None)
    with pytest.raises(HTTPException) as exc_info:
        await service.login("noexiste@biga.app", "Test1234!")
    assert exc_info.value.status_code == 401


async def test_login_inactive_user_raises_403():
    user = make_user(is_active=False)
    service = make_service(user)
    with pytest.raises(HTTPException) as exc_info:
        await service.login("docente@biga.app", "Test1234!")
    assert exc_info.value.status_code == 403


async def test_login_unknown_email_same_error_as_wrong_password():
    """Email inexistente y contraseña incorrecta deben dar el mismo status code
    para no revelar si el email está registrado."""
    service_no_user = make_service(user=None)
    service_wrong_pass = make_service(make_user())

    with pytest.raises(HTTPException) as e1:
        await service_no_user.login("x@biga.app", "pass")
    with pytest.raises(HTTPException) as e2:
        await service_wrong_pass.login("docente@biga.app", "wrong")

    assert e1.value.status_code == e2.value.status_code == 401
