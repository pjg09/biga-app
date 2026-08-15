from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_storage_adapter
from app.core.photos import resolve_photo_url
from app.models.user import User
from app.repositories.agendatorio_repository import AgendatorioRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.students import StudentCreate, StudentDetailResponse, StudentResponse, StudentSearchResult
from app.services.agendatorio_service import AgendatorioService
from app.services.student_service import StudentService

router = APIRouter(prefix="/students", tags=["students"])


def get_agendatorio_service(
    db: AsyncSession = Depends(get_db),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
) -> AgendatorioService:
    return AgendatorioService(
        agendatorio_repo=AgendatorioRepository(db),
        student_repo=StudentRepository(db),
        guardian_repo=GuardianRepository(db),
        storage=storage,
    )


def get_student_service(
    db: AsyncSession = Depends(get_db),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
) -> StudentService:
    return StudentService(StudentRepository(db), storage, GuardianRepository(db))


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentCreate,
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    return await service.create_student(data=body, institution_id=current_user.institution_id)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    grade_id: UUID | None = None,
    group_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    """"Mis estudiantes". Al docente le devuelve solo los de sus salones.

    No confundir con `GET /students/search`, que sigue alcanzando a toda la
    institución: convivencia necesita poder registrar a cualquier estudiante.

    `grade_id`/`group_id` filtran el listado del administrador (ver
    `StudentService.list_students`); el de docente/operador PAE los ignora.
    """
    return await service.list_students(
        institution_id=current_user.institution_id,
        user_id=current_user.id,
        role=current_user.role,
        grade_id=grade_id,
        group_id=group_id,
    )


@router.post("/{student_id}/photo", response_model=StudentResponse)
async def upload_student_photo(
    student_id: UUID,
    photo: UploadFile = File(..., description="Imagen del estudiante (JPG, PNG o WEBP)"),
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    data = await photo.read()
    return await service.set_photo(
        student_id=student_id,
        institution_id=current_user.institution_id,
        data=data,
        content_type=photo.content_type or "",
    )


@router.get("/search", response_model=list[StudentSearchResult])
async def search_students(
    # `q` es opcional: si se pasa grade_id/group_id, se puede navegar por
    # grado/salón sin escribir nombre (búsqueda por grado/salón del scope 3.3).
    q: str = Query("", max_length=100),
    group_id: UUID | None = None,
    grade_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
):
    rows = await service.search_students(
        q=q,
        institution_id=current_user.institution_id,
        group_id=group_id,
        grade_id=grade_id,
    )
    return [
        StudentSearchResult(
            id=row.id,
            full_name=row.full_name,
            document_number=row.document_number,
            photo_url=resolve_photo_url(storage, row.photo_url),
            group_name=row.group_name,
            grade_name=row.grade_name,
        )
        for row in rows
    ]


@router.get("/{student_id}", response_model=StudentDetailResponse)
async def get_student_detail(
    student_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    """Ficha de detalle del módulo de Aula (docente/operador PAE).

    Declarado DESPUÉS de `/search` a propósito: si fuera el primer `GET
    /{student_id}` del router, "search" haría match acá como si fuera un
    student_id y nunca llegaría a `search_students` (Starlette resuelve por
    orden de registro, no por especificidad de patrón).
    """
    return await service.get_student_detail(
        student_id=student_id,
        institution_id=current_user.institution_id,
        user_id=current_user.id,
        role=current_user.role,
    )
