from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.security import hash_password
from app.models.class_period import ClassPeriod
from app.models.grade import Grade
from app.models.group import Group
from app.models.guardian import Guardian
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user import User
from app.models.user_group import UserGroup
from app.repositories.admin_management_repository import AdminManagementRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.admin import (
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


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


class AdminManagementService:
    def __init__(
        self,
        repo: AdminManagementRepository,
        student_repo: StudentRepository,
        guardian_repo: GuardianRepository,
    ):
        self.repo = repo
        self.student_repo = student_repo
        self.guardian_repo = guardian_repo

    # --- Personal (usuarios) ---

    async def create_user(self, data: AdminUserCreate, institution_id: UUID) -> AdminUserResponse:
        if await self.repo.get_user_by_email(data.email.lower().strip()):
            raise _conflict("Ya existe un usuario con ese correo")
        user = User(
            id=uuid4(),
            institution_id=institution_id,
            document_number=data.document_number.strip(),
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=data.email.lower().strip(),
            hashed_password=hash_password(data.password),
            role=data.role,
            is_active=True,
        )
        saved = await self.repo.create_user(user)
        return AdminUserResponse.model_validate(saved)

    async def list_users(self, institution_id: UUID) -> list[AdminUserResponse]:
        return [AdminUserResponse.model_validate(u) for u in await self.repo.list_users(institution_id)]

    # --- Grados ---

    async def create_grade(self, data: GradeCreate, institution_id: UUID) -> GradeResponse:
        if await self.repo.get_grade_by_level(institution_id, data.level):
            raise _conflict(f"Ya existe un grado con el nivel {data.level}")
        grade = Grade(id=uuid4(), institution_id=institution_id, name=data.name.strip(), level=data.level)
        return GradeResponse.model_validate(await self.repo.create_grade(grade))

    async def list_grades(self, institution_id: UUID) -> list[GradeResponse]:
        return [GradeResponse.model_validate(g) for g in await self.repo.list_grades(institution_id)]

    # --- Grupos ---

    async def create_group(self, data: GroupCreate, institution_id: UUID) -> GroupResponse:
        grade = await self.repo.get_grade(data.grade_id, institution_id)
        if not grade:
            raise _not_found("Grado no encontrado en esta institución")
        if await self.repo.get_group_by_unique(data.grade_id, data.name.strip(), data.academic_year):
            raise _conflict("Ya existe ese grupo para el grado y año indicados")
        group = Group(
            id=uuid4(),
            institution_id=institution_id,
            grade_id=data.grade_id,
            name=data.name.strip(),
            academic_year=data.academic_year,
        )
        saved = await self.repo.create_group(group)
        return GroupResponse(
            id=saved.id, grade_id=saved.grade_id, grade_name=grade.name,
            name=saved.name, academic_year=saved.academic_year,
        )

    async def list_groups(self, institution_id: UUID) -> list[GroupResponse]:
        return [
            GroupResponse(
                id=g.id, grade_id=g.grade_id, grade_name=grade_name,
                name=g.name, academic_year=g.academic_year,
            )
            for g, grade_name in await self.repo.list_groups(institution_id)
        ]

    # --- Matrícula estudiante-grupo ---

    async def enroll_student_in_group(
        self, data: StudentGroupCreate, institution_id: UUID
    ) -> StudentGroupResponse:
        if not await self.repo.get_student(data.student_id, institution_id):
            raise _not_found("Estudiante no encontrado en esta institución")
        if not await self.repo.get_group(data.group_id, institution_id):
            raise _not_found("Grupo no encontrado en esta institución")
        if await self.repo.get_student_group(data.student_id, data.academic_year):
            raise _conflict("El estudiante ya está matriculado en un grupo ese año")
        sg = StudentGroup(
            id=uuid4(),
            student_id=data.student_id,
            group_id=data.group_id,
            academic_year=data.academic_year,
            is_active=True,
        )
        return StudentGroupResponse.model_validate(await self.repo.create_student_group(sg))

    # --- Alta completa de estudiante (estudiante + matrícula opcional + acudientes) ---

    async def create_student_full(
        self, data: AdminStudentCreate, institution_id: UUID
    ) -> StudentResponse:
        """Crea Student + matrícula opcional en `student_groups` + Guardians en una
        sola transacción (todo o nada, vía el auto-commit/rollback de `get_db()`).

        `grade_id` nunca llega hasta acá: `student_groups` no tiene esa columna, el
        grado es puramente un filtro de UI para acotar el <select> de salón. La regla
        "exactamente un acudiente primario" no se revalida acá — ya la aplicó el
        `model_validator` de `AdminStudentCreate` antes de que la request llegara.
        """
        if await self.student_repo.get_by_document(institution_id, data.document_number):
            raise _conflict("Ya existe un estudiante con este documento en la institución")

        group = None
        if data.group_id is not None:
            group = await self.repo.get_group(data.group_id, institution_id)
            if not group:
                raise _not_found("Grupo no encontrado en esta institución")

        student = Student(
            id=uuid4(),
            institution_id=institution_id,
            document_number=data.document_number,
            first_name=data.first_name,
            last_name=data.last_name,
            birth_date=data.birth_date,
            photo_url=None,
            is_active=True,
        )
        saved = await self.student_repo.create(student)

        if group is not None:
            await self.repo.create_student_group(
                StudentGroup(
                    id=uuid4(),
                    student_id=saved.id,
                    group_id=group.id,
                    academic_year=date.today().year,
                    is_active=True,
                )
            )

        for g in data.guardians:
            await self.guardian_repo.create(
                Guardian(
                    id=uuid4(),
                    student_id=saved.id,
                    full_name=g.full_name,
                    relationship=g.relationship,
                    email=str(g.email),  # EmailStr -> str, si no el flush falla
                    phone=g.phone,
                    is_primary=g.is_primary,
                )
            )

        resp = StudentResponse.model_validate(saved)
        # `grade_name`/`group_name` se dejan en None a propósito: el front vuelve a
        # pedir el listado completo (con join) después de crear, así que no vale la
        # pena un lookup extra acá solo para mostrarlo un instante.
        resp.grade_name = None
        resp.group_name = None
        return resp

    # --- Horarios ---

    async def create_class_period(
        self, data: ClassPeriodCreate, institution_id: UUID
    ) -> ClassPeriodResponse:
        if not await self.repo.get_group(data.group_id, institution_id):
            raise _not_found("Grupo no encontrado en esta institución")
        if data.start_time >= data.end_time:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "La hora de inicio debe ser menor a la de fin")
        if await self.repo.get_class_period_by_unique(data.group_id, data.period_order, data.day_of_week):
            raise _conflict("Ya existe un bloque con ese orden y día para el grupo")
        cp = ClassPeriod(
            id=uuid4(),
            institution_id=institution_id,
            group_id=data.group_id,
            name=data.name.strip(),
            period_order=data.period_order,
            start_time=data.start_time,
            end_time=data.end_time,
            day_of_week=data.day_of_week,
        )
        return ClassPeriodResponse.model_validate(await self.repo.create_class_period(cp))

    async def list_class_periods(self, group_id: UUID, institution_id: UUID) -> list[ClassPeriodResponse]:
        if not await self.repo.get_group(group_id, institution_id):
            raise _not_found("Grupo no encontrado en esta institución")
        return [
            ClassPeriodResponse.model_validate(cp)
            for cp in await self.repo.list_class_periods(group_id, institution_id)
        ]

    # --- Asignación docente-grupo ---

    async def assign_teacher(self, data: UserGroupCreate, institution_id: UUID) -> UserGroupResponse:
        user = await self.repo.get_user(data.user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")
        if not await self.repo.get_group(data.group_id, institution_id):
            raise _not_found("Grupo no encontrado en esta institución")
        if await self.repo.get_user_group(data.user_id, data.group_id, data.academic_year):
            raise _conflict("El docente ya está asignado a ese grupo ese año")
        ug = UserGroup(
            id=uuid4(),
            user_id=data.user_id,
            group_id=data.group_id,
            academic_year=data.academic_year,
        )
        saved = await self.repo.create_user_group(ug)
        return UserGroupResponse(
            id=saved.id, user_id=saved.user_id,
            user_name=f"{user.first_name} {user.last_name}",
            group_id=saved.group_id, academic_year=saved.academic_year,
        )

    async def list_teacher_assignments(self, institution_id: UUID) -> list[UserGroupResponse]:
        return [
            UserGroupResponse(
                id=ug.id, user_id=ug.user_id, user_name=name,
                group_id=ug.group_id, academic_year=ug.academic_year,
            )
            for ug, name in await self.repo.list_user_groups(institution_id)
        ]
