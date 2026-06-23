from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.models.student import Student
from app.repositories.student_repository import StudentRepository
from app.schemas.students import StudentCreate, StudentResponse


class StudentService:
    def __init__(self, repo: StudentRepository):
        self.repo = repo

    async def create_student(
        self,
        data: StudentCreate,
        institution_id: UUID,
    ) -> StudentResponse:
        existing = await self.repo.get_by_document(
            institution_id=institution_id,
            document_number=data.document_number,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un estudiante con este documento en la institución",
            )

        student = Student(
            id=uuid4(),
            institution_id=institution_id,
            document_number=data.document_number,
            first_name=data.first_name,
            last_name=data.last_name,
            birth_date=data.birth_date,
            photo_url=data.photo_url,
            is_active=True,
        )
        saved = await self.repo.create(student)
        return StudentResponse.model_validate(saved)

    async def list_students(self, institution_id: UUID) -> list[StudentResponse]:
        students = await self.repo.list_by_institution(institution_id=institution_id)
        return [StudentResponse.model_validate(s) for s in students]
