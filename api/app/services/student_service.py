from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.config import settings
from app.core.photos import ALLOWED_PHOTO_TYPES, resolve_photo_url
from app.models.enums import UserRole
from app.models.student import Student
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.guardian import GuardianResponse
from app.schemas.students import StudentCreate, StudentDetailResponse, StudentResponse


class StudentService:
    def __init__(self, repo: StudentRepository, storage: S3StorageAdapter, guardian_repo: GuardianRepository):
        self.repo = repo
        self.storage = storage
        self.guardian_repo = guardian_repo

    def _to_response(
        self,
        student: Student,
        grade_name: str | None = None,
        group_name: str | None = None,
        subject: str | None = None,
    ) -> StudentResponse:
        resp = StudentResponse.model_validate(student)
        resp.photo_url = resolve_photo_url(self.storage, student.photo_url)
        resp.grade_name = grade_name
        resp.group_name = group_name
        resp.subject = subject
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
        grade_id: UUID | None = None,
        group_id: UUID | None = None,
        include_inactive: bool = False,
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

        `grade_id`/`group_id` solo se aplican al listado del administrador: el
        de docente/operador PAE ya viene acotado a sus propios salones, que
        normalmente es un conjunto chico y no necesita este filtro.
        """
        if role in (UserRole.TEACHER, UserRole.PAE_OPERATOR):
            rows = await self.repo.list_for_teacher(
                institution_id=institution_id,
                user_id=user_id,
                academic_year=date.today().year,
            )
            return [self._to_response(s, grade_name, group_name, subject) for s, grade_name, group_name, subject in rows]

        # `include_inactive` solo llega hasta aquí, la rama del ADMIN: docente y
        # operador PAE nunca deben ver estudiantes dados de baja en su aula.
        rows = await self.repo.list_by_institution(
            institution_id=institution_id, grade_id=grade_id, group_id=group_id,
            include_inactive=include_inactive,
        )
        return [self._to_response(s, grade_name, group_name) for s, grade_name, group_name in rows]

    async def get_student_detail(
        self,
        student_id: UUID,
        institution_id: UUID,
        user_id: UUID,
        role: UserRole,
    ) -> StudentDetailResponse:
        """Ficha de detalle del módulo de Aula (docente/operador PAE).

        Mismo recorte que `list_students`: solo se puede ver el detalle de un
        estudiante que está en uno de los salones asignados a este usuario.
        No es un endpoint de administración — no expone la institución entera.
        """
        if role not in (UserRole.TEACHER, UserRole.PAE_OPERATOR):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

        row = await self.repo.get_for_teacher(
            student_id=student_id,
            institution_id=institution_id,
            user_id=user_id,
            academic_year=date.today().year,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
        student, grade_name, group_name, subject = row

        guardians = await self.guardian_repo.list_by_student(student.id)
        base = self._to_response(student, grade_name, group_name, subject)
        return StudentDetailResponse(
            **base.model_dump(),
            guardians=[GuardianResponse.model_validate(g) for g in guardians],
        )

    async def set_photo(
        self,
        student_id: UUID,
        institution_id: UUID,
        data: bytes,
        content_type: str,
    ) -> StudentResponse:
        ext = ALLOWED_PHOTO_TYPES.get(content_type)
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato no soportado. Use JPG, PNG o WEBP.",
            )
        if len(data) > settings.photo_max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"La imagen supera {settings.photo_max_upload_mb} MB",
            )
        student = await self.repo.get_by_id(student_id, institution_id)
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")

        key = f"photos/{institution_id}/{student_id}.{ext}"
        self.storage.upload(key, data, content_type)
        await self.repo.update_photo(student, key)
        return self._to_response(student)
