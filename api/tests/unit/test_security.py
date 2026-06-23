from datetime import date, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.security import (
    compute_delivery_hash,
    compute_enrollment_hash,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_delivery_hash,
    verify_enrollment_hash,
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


# ── Cadena de integridad PAE (doble hash) ─────────────────────────────

def _enrollment_args():
    return {
        "student_id": uuid4(),
        "institution_id": uuid4(),
        "academic_year": 2026,
        "enrolled_at": datetime(2026, 1, 15, 8, 30, 0),
    }


def test_enrollment_hash_is_deterministic():
    args = _enrollment_args()
    assert compute_enrollment_hash(**args) == compute_enrollment_hash(**args)


def test_enrollment_hash_is_sha256_hex():
    h = compute_enrollment_hash(**_enrollment_args())
    assert len(h) == 64
    int(h, 16)  # no lanza si es hex válido


def test_verify_enrollment_hash_accepts_valid():
    args = _enrollment_args()
    h = compute_enrollment_hash(**args)
    assert verify_enrollment_hash(**args, stored_hash=h) is True


def test_verify_enrollment_hash_rejects_tampered_year():
    args = _enrollment_args()
    h = compute_enrollment_hash(**args)
    args["academic_year"] = 2025  # manipulación
    assert verify_enrollment_hash(**args, stored_hash=h) is False


def test_delivery_hash_depends_on_enrollment_hash():
    common = {
        "student_id": uuid4(),
        "delivery_date": date(2026, 6, 12),
        "delivered_by_user_id": uuid4(),
        "created_at": datetime(2026, 6, 12, 11, 0, 0),
    }
    h1 = compute_delivery_hash(**common, enrollment_hash="a" * 64)
    h2 = compute_delivery_hash(**common, enrollment_hash="b" * 64)
    assert h1 != h2  # la cadena ata la entrega a la inscripción


def test_verify_delivery_hash_accepts_valid():
    args = {
        "student_id": uuid4(),
        "delivery_date": date(2026, 6, 12),
        "delivered_by_user_id": uuid4(),
        "created_at": datetime(2026, 6, 12, 11, 0, 0),
        "enrollment_hash": "c" * 64,
    }
    h = compute_delivery_hash(**args)
    assert verify_delivery_hash(**args, stored_hash=h) is True


def test_verify_delivery_hash_rejects_swapped_enrollment():
    args = {
        "student_id": uuid4(),
        "delivery_date": date(2026, 6, 12),
        "delivered_by_user_id": uuid4(),
        "created_at": datetime(2026, 6, 12, 11, 0, 0),
        "enrollment_hash": "c" * 64,
    }
    h = compute_delivery_hash(**args)
    args["enrollment_hash"] = "d" * 64  # inscripción distinta
    assert verify_delivery_hash(**args, stored_hash=h) is False
