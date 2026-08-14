import hashlib
import hmac
import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_otp_code(digits: int = 6) -> str:
    """Código numérico de un solo uso, con CSPRNG.

    `secrets` y no `random`: este último es un Mersenne Twister predecible a
    partir de unas pocas salidas observadas.
    """
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def _hmac_hex(message: str) -> str:
    return hmac.new(
        settings.pae_signing_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


# ── Cadena de integridad PAE (doble hash) ─────────────────────────────
#
# El módulo PAE usa dos capas de HMAC-SHA256 encadenadas para hacer cada
# registro a prueba de manipulación (tamper-evident) incluso contra quien
# tenga acceso de escritura directo a la base de datos:
#
#   capa 1 — enrollment_hash: firma la inscripción del estudiante al PAE.
#   capa 2 — delivery_hash:   firma la entrega E INCLUYE el enrollment_hash.
#
# Encadenar la segunda capa sobre la primera ata cada entrega a la
# inscripción exacta que la habilitó. Si alguien fabrica una inscripción,
# altera un año académico, o reescribe una entrega directamente en la BD,
# el hash recomputado deja de coincidir y la auditoría lo marca. La clave
# (`pae_signing_secret`) nunca se almacena en la BD, por lo que un atacante
# con acceso a las tablas no puede regenerar hashes válidos.


def compute_enrollment_hash(
    student_id: UUID,
    institution_id: UUID,
    academic_year: int,
    enrolled_at: datetime,
) -> str:
    message = f"{student_id}:{institution_id}:{academic_year}:{enrolled_at.isoformat()}"
    return _hmac_hex(message)


def verify_enrollment_hash(
    student_id: UUID,
    institution_id: UUID,
    academic_year: int,
    enrolled_at: datetime,
    stored_hash: str,
) -> bool:
    expected = compute_enrollment_hash(student_id, institution_id, academic_year, enrolled_at)
    return hmac.compare_digest(expected, stored_hash)


def compute_delivery_hash(
    student_id: UUID,
    delivery_date: date,
    delivered_by_user_id: UUID,
    created_at: datetime,
    enrollment_hash: str,
) -> str:
    message = (
        f"{student_id}:{delivery_date.isoformat()}:{delivered_by_user_id}:"
        f"{created_at.isoformat()}:{enrollment_hash}"
    )
    return _hmac_hex(message)


def verify_delivery_hash(
    student_id: UUID,
    delivery_date: date,
    delivered_by_user_id: UUID,
    created_at: datetime,
    enrollment_hash: str,
    stored_hash: str,
) -> bool:
    expected = compute_delivery_hash(
        student_id, delivery_date, delivered_by_user_id, created_at, enrollment_hash
    )
    return hmac.compare_digest(expected, stored_hash)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
