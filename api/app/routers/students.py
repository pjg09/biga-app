from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_storage_adapter
from app.models.user import User
from app.repositories.agendatorio_repository import AgendatorioRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.students import StudentCreate, StudentResponse, StudentSearchResult
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


def get_student_service(db: AsyncSession = Depends(get_db)) -> StudentService:
    return StudentService(StudentRepository(db))


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    body: StudentCreate,
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    return await service.create_student(data=body, institution_id=current_user.institution_id)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    current_user: User = Depends(get_current_user),
    service: StudentService = Depends(get_student_service),
):
    return await service.list_students(institution_id=current_user.institution_id)


@router.get("/search", response_model=list[StudentSearchResult])
async def search_students(
    q: str = Query(min_length=2),
    group_id: UUID | None = None,
    grade_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
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
            photo_url=row.photo_url,
            group_name=row.group_name,
            grade_name=row.grade_name,
        )
        for row in rows
    ]
