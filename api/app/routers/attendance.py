from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_staff
from app.models.user import User
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import (
    AttendanceRecordResponse,
    AttendanceSubmit,
    FirstClassResponse,
    JustificationInfo,
    JustificationMessage,
    JustificationSubmit,
    ScheduleItem,
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


def get_attendance_service(db: AsyncSession = Depends(get_db)) -> AttendanceService:
    return AttendanceService(AttendanceRepository(db))


# --- Docente / operador PAE (autenticado) ---

@router.get("/first-class/today", response_model=FirstClassResponse)
async def get_first_class(
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_first_class(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
    )


@router.post("/first-class", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_201_CREATED)
async def submit_attendance(
    body: AttendanceSubmit,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.submit_attendance(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        data=body,
    )


@router.post("/records/{record_id}/arrived", response_model=AttendanceRecordResponse)
async def mark_arrived(
    record_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.mark_arrived(record_id=record_id, institution_id=current_user.institution_id)


@router.get("/schedule", response_model=list[ScheduleItem])
async def my_schedule(
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_schedule(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
    )


@router.get("/justifications", response_model=list[JustificationMessage])
async def my_justifications(
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.list_justifications(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
    )


# --- Justificación pública (sin autenticación; el token UUID es la autorización) ---

@router.get("/justify/{token}", response_model=JustificationInfo)
async def justification_info(
    token: UUID,
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_justification_info(token)


@router.post("/justify/{token}", response_model=JustificationInfo)
async def submit_justification(
    token: UUID,
    body: JustificationSubmit,
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.submit_justification(token=token, reason=body.reason)
