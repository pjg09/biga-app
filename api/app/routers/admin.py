from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin, require_leads_reader
from app.models.enums import NotificationStatus
from app.models.user import User
from app.repositories.admin_management_repository import AdminManagementRepository
from app.repositories.admin_repository import AdminRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.admin import (
    AdminStats,
    AdminStudentCreate,
    AdminUserCreate,
    AdminUserResponse,
    ClassPeriodCreate,
    ClassPeriodResponse,
    GradeCreate,
    GradeResponse,
    GroupCreate,
    GroupResponse,
    StudentGroupCreate,
    StudentGroupResponse,
    UserGroupCreate,
    UserGroupResponse,
)
from app.schemas.students import StudentResponse
from app.schemas.leads import LeadsPage
from app.services.admin_management_service import AdminManagementService
from app.services.admin_service import AdminService
from app.services.lead_service import LeadService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(AdminRepository(db))


def get_mgmt_service(db: AsyncSession = Depends(get_db)) -> AdminManagementService:
    return AdminManagementService(
        AdminManagementRepository(db), StudentRepository(db), GuardianRepository(db)
    )


def get_lead_service(db: AsyncSession = Depends(get_db)) -> LeadService:
    return LeadService(LeadRepository(db))


# --- Estadísticas ---

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    current_user: User = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_stats(institution_id=current_user.institution_id)


# --- Personal (usuarios) ---

@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_user(body, current_user.institution_id)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_users(current_user.institution_id)


# --- Académico: grados ---

@router.post("/grades", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
async def create_grade(
    body: GradeCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_grade(body, current_user.institution_id)


@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_grades(current_user.institution_id)


# --- Académico: grupos ---

@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_group(body, current_user.institution_id)


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_groups(current_user.institution_id)


# --- Académico: matrícula estudiante-grupo ---

@router.post("/student-groups", response_model=StudentGroupResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student_in_group(
    body: StudentGroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.enroll_student_in_group(body, current_user.institution_id)


# --- Alta completa de estudiante (estudiante + matrícula opcional + acudientes) ---

@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student_full(
    body: AdminStudentCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Distinto de `POST /students` (bare, sin restricción de rol): este crea
    Student + matrícula opcional + Guardians en una sola transacción atómica."""
    return await service.create_student_full(body, current_user.institution_id)


# --- Horarios: bloques (class_periods) ---

@router.post("/class-periods", response_model=ClassPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_class_period(
    body: ClassPeriodCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_class_period(body, current_user.institution_id)


@router.get("/class-periods", response_model=list[ClassPeriodResponse])
async def list_class_periods(
    group_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_class_periods(group_id, current_user.institution_id)


# --- Horarios: asignación docente-grupo ---

@router.post("/teacher-assignments", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
async def assign_teacher(
    body: UserGroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.assign_teacher(body, current_user.institution_id)


@router.get("/teacher-assignments", response_model=list[UserGroupResponse])
async def list_teacher_assignments(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_teacher_assignments(current_user.institution_id)


# --- Leads de la landing ---

@router.get("/leads", response_model=LeadsPage)
async def list_leads(
    status_filter: NotificationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_leads_reader),
    service: LeadService = Depends(get_lead_service),
):
    """Solicitudes de demo de la landing.

    No recibe `institution_id`: `demo_leads` es pre-tenant. El aislamiento lo da
    `require_leads_reader`, no un filtro en el WHERE.
    """
    return await service.list_leads(status=status_filter, limit=limit, offset=offset)
