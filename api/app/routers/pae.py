from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.pae_repository import PAERepository
from app.schemas.pae import (
    PAEAuditResponse,
    PAEDeliveryCreate,
    PAEDeliveryResponse,
    PAEEnrollmentCreate,
    PAEEnrollmentResponse,
    PAEStudentListItem,
    PAEWeeklyReportResponse,
)
from app.services.pae_service import PAEService
from fastapi import HTTPException, status

router = APIRouter(prefix="/pae", tags=["pae"])


def get_pae_service(db: AsyncSession = Depends(get_db)) -> PAEService:
    return PAEService(PAERepository(db), db)


def require_pae_operator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.PAE_OPERATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo operadores PAE pueden acceder a este recurso",
        )
    return current_user


@router.get("/students/today", response_model=list[PAEStudentListItem])
async def list_students_today(
    current_user: User = Depends(require_pae_operator),
    service: PAEService = Depends(get_pae_service),
):
    return await service.list_students_today(
        institution_id=current_user.institution_id,
        academic_year=date.today().year,
        delivery_date=date.today(),
    )


@router.post("/enrollments", response_model=PAEEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student(
    body: PAEEnrollmentCreate,
    current_user: User = Depends(require_pae_operator),
    service: PAEService = Depends(get_pae_service),
):
    return await service.enroll_student(
        student_id=body.student_id,
        institution_id=current_user.institution_id,
        academic_year=date.today().year,
    )


@router.post("/deliveries", response_model=PAEDeliveryResponse, status_code=status.HTTP_201_CREATED)
async def register_delivery(
    body: PAEDeliveryCreate,
    current_user: User = Depends(require_pae_operator),
    service: PAEService = Depends(get_pae_service),
):
    return await service.register_delivery(
        student_id=body.student_id,
        identification_method=body.identification_method,
        delivered_by_user_id=current_user.id,
        institution_id=current_user.institution_id,
        academic_year=date.today().year,
    )


@router.get("/report/weekly", response_model=PAEWeeklyReportResponse)
async def weekly_report(
    current_user: User = Depends(require_pae_operator),
    service: PAEService = Depends(get_pae_service),
):
    return await service.weekly_report(institution_id=current_user.institution_id)


@router.get("/audit", response_model=PAEAuditResponse)
async def audit_deliveries(
    current_user: User = Depends(require_pae_operator),
    service: PAEService = Depends(get_pae_service),
):
    return await service.audit_deliveries(institution_id=current_user.institution_id)
