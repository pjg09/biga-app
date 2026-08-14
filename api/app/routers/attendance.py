from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.dependencies import get_storage_adapter, require_staff
from app.models.user import User
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.guardian_repository import GuardianRepository
from app.schemas.attendance import (
    AbsenceDetail,
    AbsenceItem,
    AbsenceNoteCreate,
    AbsenceNoteResponse,
    AttendanceRecordResponse,
    AttendanceSubmit,
    ClassAttendanceResponse,
    JustificationDetail,
    JustificationInfo,
    JustificationMessage,
    JustificationNoteCreate,
    JustificationNoteResponse,
    JustificationSubmit,
    ScheduleItem,
    TodayClassesResponse,
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


def get_attendance_service(
    db: AsyncSession = Depends(get_db),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
) -> AttendanceService:
    return AttendanceService(AttendanceRepository(db), storage, GuardianRepository(db))


# --- Docente / operador PAE (autenticado) ---

@router.get("/today", response_model=TodayClassesResponse)
async def get_today_classes(
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_today_classes(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
    )


@router.get("/classes/{class_period_id}", response_model=ClassAttendanceResponse)
async def get_class_attendance(
    class_period_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_class_attendance(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        class_period_id=class_period_id,
    )


@router.post("", response_model=list[AttendanceRecordResponse], status_code=status.HTTP_201_CREATED)
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
    student_id: UUID | None = None,
    include_archived: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    """Excusas dirigidas al docente. Los casos cerrados se omiten por defecto."""
    return await service.list_justifications(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        student_id=student_id,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )


@router.get("/justifications/{justification_id}", response_model=JustificationDetail)
async def justification_detail(
    justification_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_justification_detail(
        justification_id=justification_id,
        institution_id=current_user.institution_id,
    )


@router.post(
    "/justifications/{justification_id}/notes",
    response_model=JustificationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_justification_note(
    justification_id: UUID,
    body: JustificationNoteCreate,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.add_justification_note(
        justification_id=justification_id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        note=body.note,
    )


@router.post("/justifications/{justification_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def close_justification(
    justification_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    """Cerrar el caso: lo saca del panel sin borrar nada."""
    await service.set_justification_archived(
        justification_id=justification_id,
        institution_id=current_user.institution_id,
        archived=True,
    )


@router.post("/justifications/{justification_id}/unarchive", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_justification(
    justification_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    await service.set_justification_archived(
        justification_id=justification_id,
        institution_id=current_user.institution_id,
        archived=False,
    )


# --- Inasistencias de primera hora sin justificar ---

@router.get("/absences", response_model=list[AbsenceItem])
async def my_unjustified_absences(
    student_id: UUID | None = None,
    include_closed: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    """Inasistencias de primera hora que el docente reportó y nadie justificó.

    Desaparecen de aquí en cuanto existe la justificación del acudiente: pasan a
    ser un caso de Mensajes.
    """
    return await service.list_unjustified_absences(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        student_id=student_id,
        include_closed=include_closed,
        skip=skip,
        limit=limit,
    )


@router.get("/absences/{record_id}", response_model=AbsenceDetail)
async def absence_detail(
    record_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_absence_detail(
        record_id=record_id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
    )


@router.post(
    "/absences/{record_id}/notes",
    response_model=AbsenceNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_absence_note(
    record_id: UUID,
    body: AbsenceNoteCreate,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.add_absence_note(
        record_id=record_id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        note=body.note,
    )


@router.post("/absences/{record_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def close_absence(
    record_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    """Cerrar el caso: el enlace venció o no hubo nada más que hacer."""
    await service.set_absence_closed(
        record_id=record_id, user_id=current_user.id,
        institution_id=current_user.institution_id, closed=True,
    )


@router.post("/absences/{record_id}/unarchive", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_absence(
    record_id: UUID,
    current_user: User = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
):
    await service.set_absence_closed(
        record_id=record_id, user_id=current_user.id,
        institution_id=current_user.institution_id, closed=False,
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
    # multipart, no JSON: el acudiente puede adjuntar un soporte junto al texto.
    reason: str = Form(...),
    attachment: UploadFile | None = File(default=None),
    service: AttendanceService = Depends(get_attendance_service),
):
    # El `reason` se valida con el mismo schema que antes; al venir de un campo
    # de formulario hay que construirlo a mano.
    try:
        body = JustificationSubmit(reason=reason)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    return await service.submit_justification(
        token=token,
        reason=body.reason,
        # Un multipart sin archivo puede llegar como parte vacía; se descarta
        # para no crear un adjunto de 0 bytes.
        attachment=attachment if attachment and attachment.filename else None,
    )
