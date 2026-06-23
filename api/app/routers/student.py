from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.repositories.student_repository import StudentRepository
from app.schemas.student import StudentCreate, StudentResponse
from app.services.student_service import StudentService

router = APIRouter(prefix="/students", tags=["students"])


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
