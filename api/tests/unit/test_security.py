from unittest.mock import patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_bcrypt_hash():
    h = hash_password("secret")
    assert h.startswith("$2b$")


def test_hash_password_different_salts():
    assert hash_password("secret") != hash_password("secret")


def test_verify_password_correct():
    h = hash_password("mypassword")
    assert verify_password("mypassword", h) is True


def test_verify_password_wrong():
    h = hash_password("mypassword")
    assert verify_password("wrong", h) is False


def test_create_access_token_contains_sub():
    token = create_access_token("user-123")
    from app.core.config import settings
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == "user-123"


def test_create_access_token_has_expiry():
    token = create_access_token("user-123")
    from app.core.config import settings
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert "exp" in payload


def test_decode_access_token_returns_subject():
    token = create_access_token("user-abc")
    assert decode_access_token(token) == "user-abc"


def test_decode_access_token_invalid_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("token.falso.aqui")
    assert exc_info.value.status_code == 401


def test_decode_access_token_tampered_raises_401():
    token = create_access_token("user-abc")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered)
    assert exc_info.value.status_code == 401
