from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.enums import GuardianRelationship
from app.models.group import Group
from app.models.student import Student
from app.schemas.admin import AdminStudentCreate
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
