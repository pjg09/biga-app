from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.photos import resolve_photo_url
from app.models.enums import UserRole
from app.models.student import Student
from app.repositories.student_repository import StudentRepository
from app.schemas.students import StudentCreate, StudentResponse

_ALLOWED_PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class StudentService:
    def __init__(self, repo: StudentRepository, storage: S3StorageAdapter):
        self.repo = repo
        self.storage = storage

    def _to_response(self, student: Student) -> StudentResponse:
        resp = StudentResponse.model_validate(student)
        resp.photo_url = resolve_photo_url(self.storage, student.photo_url)
        return resp

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
        return self._to_response(saved)

    async def list_students(
        self,
        institution_id: UUID,
        user_id: UUID,
        role: UserRole,
    ) -> list[StudentResponse]:
        """Listado de "Mis estudiantes" (módulo de Aula), acotado según el rol.

        Docente y operador PAE ven solo los estudiantes de los salones que
        tienen asignados: el operador PAE es un docente con funciones extra, y
        su módulo de Aula debe comportarse como el de cualquier docente. Solo el
        administrador ve la institución entera.

        Esto **no** afecta a los módulos del PAE: `/pae/students/today` y las
        matrículas del PAE consultan `pae_enrollments`/`pae_deliveries` filtrando
        únicamente por institución, así que el operador sigue viendo a todos los
        que reclaman o están matriculados, den o no clase con él.

        El recorte se hace aquí y no en el front: cualquiera puede llamar a
        `GET /students` a mano, y un filtro que solo vive en React no filtra nada.
        """
        if role in (UserRole.TEACHER, UserRole.PAE_OPERATOR):
            students = await self.repo.list_for_teacher(
                institution_id=institution_id,
                user_id=user_id,
                academic_year=date.today().year,
            )
        else:
            students = await self.repo.list_by_institution(institution_id=institution_id)
        return [self._to_response(s) for s in students]

    async def set_photo(
        self,
        student_id: UUID,
        institution_id: UUID,
        data: bytes,
        content_type: str,
    ) -> StudentResponse:
        ext = _ALLOWED_PHOTO_TYPES.get(content_type)
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato no soportado. Use JPG, PNG o WEBP.",
            )
        student = await self.repo.get_by_id(student_id, institution_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")

        key = f"photos/{institution_id}/{student_id}.{ext}"
        self.storage.upload(key, data, content_type)
        await self.repo.update_photo(student, key)
        return self._to_response(student)
