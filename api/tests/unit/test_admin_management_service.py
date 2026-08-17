from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.enums import GuardianRelationship
from app.models.class_period import ClassPeriod
from app.models.group import Group
from app.models.user import User
from app.models.student import Student
from app.core.security import verify_password
from app.models.enums import UserRole
from app.schemas.admin import (
    AdminStudentCreate,
    AdminUserCreate,
    AdminUserUpdate,
    ClassPeriodCreate,
    ClassPeriodUpdate,
    PAEEnrollmentAdd,
)
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


def make_service_with_pae():
    """Como `make_service`, pero devolviendo también el repo del PAE: las
    pruebas de inscripción necesitan afirmar sobre él (que reactiva en vez de
    recrear la firma)."""
    repo, student_repo, guardian_repo, pae_repo = (AsyncMock() for _ in range(4))
    service = AdminManagementService(repo, student_repo, guardian_repo, pae_repo, MagicMock())
    return service, repo, student_repo, guardian_repo, pae_repo


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


# --- Horarios: el `period_order` es derivado de la hora de inicio ---


def make_period_mock(start: str, end: str, order: int, day: int = 1, name: str = "Clase"):
    cp = MagicMock(spec=ClassPeriod)
    cp.id = uuid4()
    cp.group_id = uuid4()
    cp.subject_id = None
    cp.user_id = uuid4()
    cp.name = name
    cp.period_order = order
    cp.day_of_week = day
    cp.start_time = time(*map(int, start.split(":")))
    cp.end_time = time(*map(int, end.split(":")))
    return cp


def make_period_create(start: str, end: str, **overrides) -> ClassPeriodCreate:
    base = dict(
        group_id=uuid4(), day_of_week=1, name="Clase",
        start_time=time(*map(int, start.split(":"))),
        end_time=time(*map(int, end.split(":"))),
        user_id=uuid4(),
    )
    base.update(overrides)
    return ClassPeriodCreate(**base)


async def test_create_period_rejects_time_overlap():
    """El 409 legible lo da el service; el EXCLUDE de la BD es la red de abajo."""
    service, repo, *_ = make_service()
    repo.get_group.return_value = MagicMock(spec=Group)
    repo.find_overlapping_period.return_value = make_period_mock(
        "07:50", "09:30", 2, name="Matemáticas"
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_class_period(make_period_create("08:00", "09:00"), uuid4())

    assert exc.value.status_code == 409
    assert "Matemáticas" in exc.value.detail
    assert "07:50" in exc.value.detail
    repo.create_class_period.assert_not_called()


async def test_renumber_day_orders_by_start_time_in_two_phases():
    """Un bloque insertado a primera hora se lleva el orden 1, y el resto baja.

    Las dos fases importan: `UNIQUE(group, orden, día)` no es DEFERRABLE, así
    que sin el desplazamiento previo la permutación choca a mitad de camino.
    """
    service, repo, *_ = make_service()
    tarde = make_period_mock("07:00", "07:50", 1)
    temprano = make_period_mock("06:00", "06:45", 2)
    repo.list_periods_of_day.return_value = [temprano, tarde]  # ya vienen por hora

    ordenes_tras_primera_fase = []
    async def spy_flush():
        ordenes_tras_primera_fase.append([temprano.period_order, tarde.period_order])
    repo.flush.side_effect = spy_flush

    await service._renumber_day(uuid4(), 1)

    assert ordenes_tras_primera_fase[0] == [1000, 1001]   # fuera del rango en uso
    assert [temprano.period_order, tarde.period_order] == [1, 2]
    assert repo.flush.await_count == 2


async def test_delete_period_renumbers_the_day():
    """Borrar la clase de primera hora no puede dejar el día sin `period_order`
    = 1: es la condición que dispara la notificación al acudiente."""
    service, repo, *_ = make_service()
    cp = make_period_mock("07:00", "07:50", 1)
    repo.get_class_period.return_value = cp
    repo.count_attendance_for_period.return_value = 0
    repo.list_periods_of_day.return_value = [make_period_mock("07:50", "08:40", 2)]

    await service.delete_class_period(cp.id, uuid4())

    repo.delete_class_period.assert_awaited_once()
    repo.list_periods_of_day.assert_awaited_once_with(cp.group_id, cp.day_of_week)


# --- Horarios: un docente no puede estar en dos salones a la vez ---


async def test_create_period_rejects_teacher_already_busy():
    """El invariante del salón no cubre al docente: son dos cosas distintas.

    Sin este chequeo, el mismo profesor acumulaba cuatro primeras horas
    simultáneas en cuatro salones y Asistencia se las mostraba todas.
    """
    service, repo, *_ = make_service()
    repo.get_group.return_value = MagicMock(spec=Group)
    repo.find_overlapping_period.return_value = None        # el salón está libre
    ocupado = make_period_mock("07:00", "07:50", 1, name="Primera hora")
    repo.find_teacher_conflict.return_value = (ocupado, "Once", "A")
    docente = MagicMock(spec=User)
    docente.first_name, docente.last_name = "Carlos", "Docente"
    docente.is_active = True
    repo.get_user.return_value = docente

    with pytest.raises(HTTPException) as exc:
        await service.create_class_period(make_period_create("07:20", "08:10"), uuid4())

    assert exc.value.status_code == 409
    assert "Carlos Docente" in exc.value.detail
    assert "Once A" in exc.value.detail
    repo.create_class_period.assert_not_called()


async def test_create_period_allows_teacher_in_a_free_slot():
    service, repo, *_ = make_service()
    repo.get_group.return_value = MagicMock(spec=Group)
    repo.find_overlapping_period.return_value = None
    repo.find_teacher_conflict.return_value = None
    docente = MagicMock(spec=User)
    docente.is_active = True
    repo.get_user.return_value = docente
    repo.get_user_group.return_value = MagicMock()
    repo.max_period_order.return_value = 0
    repo.list_periods_of_day.return_value = []

    await service.create_class_period(make_period_create("07:20", "08:10"), uuid4())

    repo.create_class_period.assert_awaited_once()


async def test_update_period_excludes_itself_from_the_teacher_check():
    """Editar la etiqueta de un bloque sin tocar la hora no puede dar 409 contra
    sí mismo: el bloque que se está editando se excluye de la búsqueda."""
    service, repo, *_ = make_service()
    cp = make_period_mock("07:00", "07:50", 1)
    repo.get_class_period.return_value = cp
    repo.find_overlapping_period.return_value = None
    repo.find_teacher_conflict.return_value = None
    docente = MagicMock(spec=User)
    docente.is_active = True
    repo.get_user.return_value = docente
    repo.get_user_group.return_value = MagicMock()
    repo.list_periods_of_day.return_value = [cp]

    await service.update_class_period(
        cp.id, ClassPeriodUpdate(name="Otra etiqueta", start_time=time(7, 0),
                                 end_time=time(7, 50), user_id=uuid4()),
        uuid4(),
    )

    assert repo.find_teacher_conflict.await_args.kwargs["exclude_id"] == cp.id


# --- PAE: inscritos desde la consola de admin ---


def make_enrollment_mock(is_active: bool = True):
    e = MagicMock()
    e.is_active = is_active
    e.enrollment_hash = "hash-original"
    return e


def make_student_mock(active: bool = True):
    s = MagicMock(spec=Student)
    s.id = uuid4()
    s.first_name, s.last_name = "Ana", "Gómez"
    s.is_active = active
    return s


async def test_add_pae_enrollment_rejects_inactive_student():
    """Un estudiante dado de baja no puede entrar al PAE: se le pedirían
    raciones que nadie va a reclamar."""
    service, repo, *_ = make_service()
    repo.get_student.return_value = make_student_mock(active=False)

    with pytest.raises(HTTPException) as exc:
        await service.add_pae_enrollment(PAEEnrollmentAdd(student_id=uuid4()), uuid4())

    assert exc.value.status_code == 409
    assert "dado de baja" in exc.value.detail


async def test_add_pae_enrollment_rejects_duplicate():
    service, repo, _, _, pae_repo = make_service_with_pae()
    repo.get_student.return_value = make_student_mock()
    pae_repo.get_any_enrollment.return_value = make_enrollment_mock(is_active=True)

    with pytest.raises(HTTPException) as exc:
        await service.add_pae_enrollment(PAEEnrollmentAdd(student_id=uuid4()), uuid4())

    assert exc.value.status_code == 409
    assert "ya está inscrito" in exc.value.detail


async def test_add_pae_enrollment_reactivates_instead_of_recreating():
    """Reinscribir a quien estuvo de baja **reactiva la fila**: `enrolled_at` y
    `enrollment_hash` son la capa 1 de la cadena de integridad del PAE, y las
    entregas ya registradas encadenan su hash con él. Crear una fila nueva
    borraría la fecha real de ingreso e invalidaría esas entregas."""
    service, repo, _, _, pae_repo = make_service_with_pae()
    student = make_student_mock()
    repo.get_student.return_value = student
    enrollment = make_enrollment_mock(is_active=False)
    pae_repo.get_any_enrollment.return_value = enrollment
    repo.list_pae_enrollments.return_value = [{
        "student_id": student.id, "document_number": "1001", "first_name": "Ana",
        "last_name": "Gómez", "photo_url": None, "grade_name": None, "group_name": None,
        "academic_year": 2026, "enrolled_at": datetime(2026, 3, 1, 7, 0),
        "is_active": True, "student_is_active": True, "last_delivery": None,
    }]

    await service.add_pae_enrollment(PAEEnrollmentAdd(student_id=student.id), uuid4())

    assert enrollment.is_active is True
    pae_repo.save_enrollment.assert_awaited_once()
    pae_repo.create_enrollment.assert_not_called()   # no se recrea la firma
    assert enrollment.enrollment_hash == "hash-original"


async def test_set_pae_enrollment_active_requires_an_enrollment():
    service, repo, _, _, pae_repo = make_service_with_pae()
    pae_repo.get_any_enrollment.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.set_pae_enrollment_active(uuid4(), uuid4(), active=False)

    assert exc.value.status_code == 404
