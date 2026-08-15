from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.enums import GuardianRelationship
from app.models.group import Group
from app.models.user import User
from app.models.student import Student
from app.core.security import verify_password
from app.models.enums import UserRole
from app.schemas.admin import AdminStudentCreate, AdminUserCreate, AdminUserUpdate
from app.schemas.guardian import GuardianCreate
from app.services.admin_management_service import AdminManagementService


def make_guardian(is_primary=True, **overrides) -> dict:
    base = dict(
        full_name="Luisa Gómez",
        relationship=GuardianRelationship.MADRE,
        email="luisa@example.com",
        phone="3001234567",
        is_primary=is_primary,
    )
    base.update(overrides)
    return base


def make_create_data(**overrides) -> AdminStudentCreate:
    base = dict(
        document_number="1002345678",
        first_name="Ana",
        last_name="Gómez",
        birth_date=date(2015, 3, 10),
        group_id=None,
        guardians=[GuardianCreate(**make_guardian())],
    )
    base.update(overrides)
    return AdminStudentCreate(**base)


def make_saved_student() -> Student:
    student = MagicMock(spec=Student)
    student.id = uuid4()
    student.document_number = "1002345678"
    student.first_name = "Ana"
    student.last_name = "Gómez"
    student.birth_date = date(2015, 3, 10)
    student.photo_url = None
    student.is_active = True
    student.created_at = datetime(2026, 8, 14, 12, 0, 0)
    return student


def make_service():
    repo = AsyncMock()
    student_repo = AsyncMock()
    guardian_repo = AsyncMock()
    pae_repo = AsyncMock()
    storage = MagicMock()
    service = AdminManagementService(repo, student_repo, guardian_repo, pae_repo, storage)
    return service, repo, student_repo, guardian_repo


# --- Validación de forma (AdminStudentCreate.exactly_one_primary) ---


def test_rejects_zero_primary_guardians():
    with pytest.raises(ValidationError, match="exactamente un acudiente"):
        make_create_data(guardians=[GuardianCreate(**make_guardian(is_primary=False))])


def test_rejects_two_primary_guardians():
    with pytest.raises(ValidationError, match="exactamente un acudiente"):
        make_create_data(
            guardians=[
                GuardianCreate(**make_guardian(is_primary=True)),
                GuardianCreate(**make_guardian(is_primary=True, email="otro@example.com")),
            ]
        )


def test_accepts_exactly_one_primary():
    data = make_create_data(
        guardians=[
            GuardianCreate(**make_guardian(is_primary=True)),
            GuardianCreate(**make_guardian(is_primary=False, email="otro@example.com")),
        ]
    )
    assert sum(1 for g in data.guardians if g.is_primary) == 1


# --- AdminManagementService.create_student_full ---


async def test_conflict_on_duplicate_document():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = MagicMock(spec=Student)

    with pytest.raises(HTTPException) as exc:
        await service.create_student_full(make_create_data(), uuid4())

    assert exc.value.status_code == 409
    student_repo.create.assert_not_called()
    guardian_repo.create.assert_not_called()


async def test_not_found_group():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = None
    repo.get_group.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.create_student_full(make_create_data(group_id=uuid4()), uuid4())

    assert exc.value.status_code == 404
    # El grupo se valida ANTES de crear el estudiante: sin esto, un group_id
    # inválido dejaría un flush() desperdiciado (igual se revierte, pero no debe
    # hacerse innecesariamente).
    student_repo.create.assert_not_called()


async def test_without_group_skips_enrollment():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = None
    student_repo.create.return_value = make_saved_student()

    await service.create_student_full(make_create_data(group_id=None), uuid4())

    repo.create_student_group.assert_not_called()


async def test_creates_one_guardian_per_input():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = None
    student_repo.create.return_value = make_saved_student()

    data = make_create_data(
        guardians=[
            GuardianCreate(**make_guardian(is_primary=True)),
            GuardianCreate(**make_guardian(is_primary=False, email="otro@example.com")),
        ]
    )
    await service.create_student_full(data, uuid4())

    assert guardian_repo.create.call_count == 2
    saved_primaries = [call.args[0].is_primary for call in guardian_repo.create.call_args_list]
    assert saved_primaries == [True, False]


async def test_academic_year_is_current_year():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = None
    saved_student = make_saved_student()
    student_repo.create.return_value = saved_student

    group = MagicMock(spec=Group)
    group.id = uuid4()
    repo.get_group.return_value = group

    await service.create_student_full(make_create_data(group_id=group.id), uuid4())

    created_sg = repo.create_student_group.call_args.args[0]
    assert created_sg.academic_year == date.today().year
    assert created_sg.group_id == group.id
    assert created_sg.student_id == saved_student.id


async def test_response_has_no_grade_or_group_name():
    service, repo, student_repo, guardian_repo = make_service()
    student_repo.get_by_document.return_value = None
    student_repo.create.return_value = make_saved_student()

    resp = await service.create_student_full(make_create_data(), uuid4())

    assert resp.grade_name is None
    assert resp.group_name is None


# --- Personal: el admin nunca fija contraseñas (ver docs/admin.md) ---


def make_user_create(**overrides) -> AdminUserCreate:
    base = dict(
        first_name="Carla",
        last_name="Ruiz",
        document_number="1088",
        email="Carla.Ruiz@Iedemo.edu.co",
        role=UserRole.TEACHER,
    )
    base.update(overrides)
    return AdminUserCreate(**base)


def test_user_create_schema_rejects_password():
    """Si alguien reintroduce `password` en el payload, debe ser ignorado, no aceptado."""
    data = AdminUserCreate(**{**make_user_create().model_dump(), "password": "loquesea123"})
    assert not hasattr(data, "password")


def test_user_update_schema_rejects_password():
    data = AdminUserUpdate(
        first_name="Carla", last_name="Ruiz", document_number="1088",
        email="carla@iedemo.edu.co", role=UserRole.TEACHER,
    )
    assert not hasattr(data, "password")


async def test_create_user_generates_hashed_temp_password(monkeypatch):
    service, repo, *_ = make_service()
    repo.get_user_by_email.return_value = None
    repo.get_user_by_document.return_value = None
    def persist(user):
        # `created_at` es server_default: en un objeto sin flush sigue a None y
        # AdminUserResponse lo exige. Se simula lo que devolvería la BD.
        user.created_at = datetime(2026, 8, 15, 12, 0, 0)
        return user

    repo.create_user.side_effect = persist

    sent = {}
    monkeypatch.setattr(
        "app.jobs.auth_jobs.notify_staff_welcome.apply_async",
        lambda args, **kw: sent.update(args=args, argsrepr=kw.get("argsrepr")),
    )

    await service.create_user(make_user_create(), uuid4())

    saved = repo.create_user.call_args[0][0]
    temp_password = sent["args"][2]
    # Solo se persiste el bcrypt, y ese bcrypt corresponde a la clave enviada.
    assert saved.hashed_password.startswith("$2b$")
    assert saved.hashed_password != temp_password
    assert verify_password(temp_password, saved.hashed_password)
    # La clave no debe poder deducirse de lo que Celery imprime en los logs.
    assert temp_password not in sent["argsrepr"]


async def test_update_user_never_touches_the_password(monkeypatch):
    service, repo, *_ = make_service()
    existing = MagicMock(spec=User)
    existing.id = uuid4()
    existing.hashed_password = "$2b$12$hash-original-intacto"
    existing.first_name, existing.last_name = "Carla", "Ruiz"
    existing.document_number, existing.email = "1088", "carla@iedemo.edu.co"
    existing.role, existing.is_active = UserRole.TEACHER, True
    existing.photo_url = None
    existing.created_at = datetime(2026, 8, 15, 12, 0, 0)
    repo.get_user.return_value = existing
    repo.get_user_by_email.return_value = None
    repo.get_user_by_document.return_value = None

    await service.update_user(
        existing.id,
        AdminUserUpdate(
            first_name="Carla", last_name="Ruiz", document_number="1088",
            email="carla@iedemo.edu.co", role=UserRole.ADMIN,
        ),
        uuid4(),
        current_user_id=uuid4(),
    )

    assert existing.hashed_password == "$2b$12$hash-original-intacto"


def make_admin_mock():
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.first_name, u.last_name = "Sofía", "Admin"
    u.document_number, u.email = "9001", "admin@iedemo.edu.co"
    u.role, u.is_active = UserRole.ADMIN, True
    u.photo_url = None
    u.hashed_password = "$2b$12$loquesea"
    u.created_at = datetime(2026, 8, 15, 12, 0, 0)
    return u


def make_update(role: UserRole) -> AdminUserUpdate:
    return AdminUserUpdate(
        first_name="Sofía", last_name="Admin", document_number="9001",
        email="admin@iedemo.edu.co", role=role,
    )


async def test_admin_cannot_demote_himself():
    """Autobloqueo por la puerta del PUT: quitarse el rol ADMIN a uno mismo."""
    service, repo, *_ = make_service()
    me = make_admin_mock()
    repo.get_user.return_value = me
    repo.get_user_by_email.return_value = None
    repo.get_user_by_document.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.update_user(
            me.id, make_update(UserRole.TEACHER), uuid4(), current_user_id=me.id
        )

    assert exc.value.status_code == 409
    repo.save_user.assert_not_called()
    assert me.role == UserRole.ADMIN  # no se tocó nada


async def test_admin_can_edit_himself_keeping_the_role():
    """La guarda solo debe frenar el cambio de rol, no la edición normal."""
    service, repo, *_ = make_service()
    me = make_admin_mock()
    repo.get_user.return_value = me
    repo.get_user_by_email.return_value = None
    repo.get_user_by_document.return_value = None

    await service.update_user(
        me.id, make_update(UserRole.ADMIN), uuid4(), current_user_id=me.id
    )

    repo.save_user.assert_called_once()


async def test_another_admin_can_demote_a_second_admin():
    """Degradar a OTRO admin sigue permitido: quien llama sigue siendo admin."""
    service, repo, *_ = make_service()
    other = make_admin_mock()
    repo.get_user.return_value = other
    repo.get_user_by_email.return_value = None
    repo.get_user_by_document.return_value = None

    await service.update_user(
        other.id, make_update(UserRole.TEACHER), uuid4(), current_user_id=uuid4()
    )

    assert other.role == UserRole.TEACHER
    repo.save_user.assert_called_once()
