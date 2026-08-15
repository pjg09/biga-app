from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from datetime import datetime as PyDatetime

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.photos import resolve_photo_url
from app.core.security import compute_enrollment_hash, hash_password
from app.models.class_period import ClassPeriod
from app.models.grade import Grade
from app.models.group import Group
from app.models.guardian import Guardian
from app.models.pae import PAEEnrollment
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.subject import Subject
from app.models.user import User
from app.models.user_group import UserGroup
from app.repositories.admin_management_repository import AdminManagementRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.pae_repository import PAERepository
from app.repositories.student_repository import StudentRepository
from app.schemas.admin import (
    AdminGuardianUpdate,
    AdminStudentCreate,
    AdminStudentDetailResponse,
    AdminStudentUpdate,
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    ClassPeriodCreate,
    ClassPeriodResponse,
    GradeCreate,
    GradeResponse,
    GroupCreate,
    GroupResponse,
    StudentGroupCreate,
    StudentGroupResponse,
    SubjectCreate,
    SubjectResponse,
    UserGroupCreate,
    UserGroupResponse,
)
from app.schemas.guardian import GuardianResponse
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
        pae_repo: PAERepository,
        storage: S3StorageAdapter,
    ):
        self.repo = repo
        self.student_repo = student_repo
        self.guardian_repo = guardian_repo
        self.pae_repo = pae_repo
        self.storage = storage

    # --- Personal (usuarios) ---

    async def create_user(self, data: AdminUserCreate, institution_id: UUID) -> AdminUserResponse:
        if await self.repo.get_user_by_email(data.email.lower().strip()):
            raise _conflict("Ya existe un usuario con ese correo")
        document_number = data.document_number.strip()
        if await self.repo.get_user_by_document(institution_id, document_number):
            raise _conflict("Ya existe un usuario con este documento en la institución")
        user = User(
            id=uuid4(),
            institution_id=institution_id,
            document_number=document_number,
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

    async def get_user_detail(self, user_id: UUID, institution_id: UUID) -> AdminUserResponse:
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")
        return AdminUserResponse.model_validate(user)

    async def update_user(
        self, user_id: UUID, data: AdminUserUpdate, institution_id: UUID
    ) -> AdminUserResponse:
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")

        email = data.email.lower().strip()
        existing_email = await self.repo.get_user_by_email(email)
        if existing_email and existing_email.id != user.id:
            raise _conflict("Ya existe un usuario con ese correo")

        document_number = data.document_number.strip()
        existing_doc = await self.repo.get_user_by_document(institution_id, document_number)
        if existing_doc and existing_doc.id != user.id:
            raise _conflict("Ya existe un usuario con este documento en la institución")

        user.first_name = data.first_name.strip()
        user.last_name = data.last_name.strip()
        user.document_number = document_number
        user.email = email
        user.role = data.role
        if data.password:
            user.hashed_password = hash_password(data.password)
        await self.repo.save_user(user)
        return AdminUserResponse.model_validate(user)

    # --- Grados ---

    async def create_grade(self, data: GradeCreate, institution_id: UUID) -> GradeResponse:
        if await self.repo.get_grade_by_level(institution_id, data.level):
            raise _conflict(f"Ya existe un grado con el nivel {data.level}")
        grade = Grade(id=uuid4(), institution_id=institution_id, name=data.name.strip(), level=data.level)
        return GradeResponse.model_validate(await self.repo.create_grade(grade))

    async def list_grades(self, institution_id: UUID) -> list[GradeResponse]:
        return [GradeResponse.model_validate(g) for g in await self.repo.list_grades(institution_id)]

    # --- Materias (catálogo) ---

    async def create_subject(self, data: SubjectCreate, institution_id: UUID) -> SubjectResponse:
        if await self.repo.get_subject_by_name(institution_id, data.name):
            raise _conflict("Ya existe una materia con ese nombre")
        subject = Subject(id=uuid4(), institution_id=institution_id, name=data.name)
        return SubjectResponse.model_validate(await self.repo.create_subject(subject))

    async def list_subjects(self, institution_id: UUID) -> list[SubjectResponse]:
        return [SubjectResponse.model_validate(s) for s in await self.repo.list_subjects(institution_id)]

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

        if data.is_pae_enrolled:
            await self._enroll_in_pae(saved.id, institution_id)

        resp = StudentResponse.model_validate(saved)
        # `grade_name`/`group_name` se dejan en None a propósito: el front vuelve a
        # pedir el listado completo (con join) después de crear, así que no vale la
        # pena un lookup extra acá solo para mostrarlo un instante.
        resp.grade_name = None
        resp.group_name = None
        return resp

    async def _enroll_in_pae(self, student_id: UUID, institution_id: UUID) -> None:
        """Mismo cálculo de hash que `PAEService.enroll_student` (capa 1 del PAE,
        ver docs/architecture.md) pero desde el flujo atómico de alta/edición del
        admin — por eso se reimplementa acá en vez de llamar a PAEService: esa
        clase depende de su propio Router/Service, no de AdminManagementService,
        y esto necesita correr DENTRO de la misma transacción que crea al
        estudiante (todo o nada).
        """
        academic_year = date.today().year
        now = PyDatetime.now()
        enrollment_hash = compute_enrollment_hash(
            student_id=student_id,
            institution_id=institution_id,
            academic_year=academic_year,
            enrolled_at=now,
        )
        await self.pae_repo.create_enrollment(
            PAEEnrollment(
                id=uuid4(),
                student_id=student_id,
                institution_id=institution_id,
                academic_year=academic_year,
                is_active=True,
                enrolled_at=now,
                enrollment_hash=enrollment_hash,
            )
        )

    async def get_student_detail(self, student_id: UUID, institution_id: UUID) -> AdminStudentDetailResponse:
        row = await self.student_repo.get_by_id_with_group(student_id, institution_id)
        if not row:
            raise _not_found("Estudiante no encontrado")
        student, grade_id, grade_name, group_id, group_name = row

        guardians = await self.guardian_repo.list_by_student(student_id)
        enrollment = await self.pae_repo.get_any_enrollment(student_id, institution_id, date.today().year)

        return AdminStudentDetailResponse(
            id=student.id,
            document_number=student.document_number,
            first_name=student.first_name,
            last_name=student.last_name,
            birth_date=student.birth_date,
            photo_url=resolve_photo_url(self.storage, student.photo_url),
            is_active=student.is_active,
            grade_id=grade_id, grade_name=grade_name,
            group_id=group_id, group_name=group_name,
            is_pae_enrolled=bool(enrollment and enrollment.is_active),
            guardians=[GuardianResponse.model_validate(g) for g in guardians],
        )

    async def update_student_full(
        self, student_id: UUID, data: AdminStudentUpdate, institution_id: UUID
    ) -> AdminStudentDetailResponse:
        """Edita Student + matrícula del año vigente + Guardians + inscripción PAE,
        todo en la misma unidad de trabajo del request (commit/rollback de
        `get_db()`) — misma filosofía "todo o nada" que `create_student_full`.

        A diferencia del alta, acá los acudientes se reconcilian por `id`: los que
        traen `id` existente se actualizan in-place, los que no traen `id` se crean,
        y los que existían pero no vienen en el payload se intentan borrar. Nunca se
        borra+recrea un acudiente con notificaciones históricas (FK desde
        `notifications_log.guardian_id`, sin `ON DELETE`) — se verifica ANTES de
        intentar el borrado (ver `GuardianRepository.has_notifications`), porque un
        `DELETE` que falla a mitad de la transacción deja la sesión async inválida
        para lo que reste del request.
        """
        student = await self.student_repo.get_by_id_with_group(student_id, institution_id)
        if not student:
            raise _not_found("Estudiante no encontrado")
        student = student[0]

        existing_doc = await self.student_repo.get_by_document(institution_id, data.document_number)
        if existing_doc and existing_doc.id != student.id:
            raise _conflict("Ya existe un estudiante con este documento en la institución")

        group = None
        if data.group_id is not None:
            group = await self.repo.get_group(data.group_id, institution_id)
            if not group:
                raise _not_found("Grupo no encontrado en esta institución")

        existing_guardians = await self.guardian_repo.list_by_student(student.id)
        existing_by_id = {g.id: g for g in existing_guardians}
        incoming_ids = {g.id for g in data.guardians if g.id is not None}

        for g in data.guardians:
            if g.id is not None and g.id not in existing_by_id:
                raise _not_found(f"Acudiente {g.id} no encontrado para este estudiante")

        to_remove = [g for g in existing_guardians if g.id not in incoming_ids]
        for g in to_remove:
            if await self.guardian_repo.has_notifications(g.id):
                raise _conflict(
                    f"No se puede quitar a {g.full_name}: tiene notificaciones registradas a su nombre"
                )

        student.document_number = data.document_number
        student.first_name = data.first_name
        student.last_name = data.last_name
        student.birth_date = data.birth_date
        await self.student_repo.save(student)

        academic_year = date.today().year
        sg = await self.repo.get_student_group(student.id, academic_year)
        if group is not None:
            if sg:
                sg.group_id = group.id
                sg.is_active = True
                await self.repo.save_student_group(sg)
            else:
                await self.repo.create_student_group(
                    StudentGroup(
                        id=uuid4(), student_id=student.id, group_id=group.id,
                        academic_year=academic_year, is_active=True,
                    )
                )
        elif sg and sg.is_active:
            sg.is_active = False
            await self.repo.save_student_group(sg)

        for g in data.guardians:
            if g.id is not None:
                row = existing_by_id[g.id]
                row.full_name = g.full_name
                row.relationship = g.relationship
                row.email = str(g.email)
                row.phone = g.phone
                row.is_primary = g.is_primary
                await self.guardian_repo.save(row)
            else:
                await self.guardian_repo.create(
                    Guardian(
                        id=uuid4(), student_id=student.id, full_name=g.full_name,
                        relationship=g.relationship, email=str(g.email),
                        phone=g.phone, is_primary=g.is_primary,
                    )
                )
        for g in to_remove:
            await self.guardian_repo.delete(g)

        enrollment = await self.pae_repo.get_any_enrollment(student.id, institution_id, academic_year)
        if data.is_pae_enrolled:
            if not enrollment:
                await self._enroll_in_pae(student.id, institution_id)
            elif not enrollment.is_active:
                enrollment.is_active = True
                await self.pae_repo.save_enrollment(enrollment)
        elif enrollment and enrollment.is_active:
            enrollment.is_active = False
            await self.pae_repo.save_enrollment(enrollment)

        return await self.get_student_detail(student.id, institution_id)

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
        subject_name = None
        if data.subject_id:
            subject = await self.repo.get_subject(data.subject_id, institution_id)
            if not subject:
                raise _not_found("Materia no encontrada en esta institución")
            subject_name = subject.name
        ug = UserGroup(
            id=uuid4(),
            user_id=data.user_id,
            group_id=data.group_id,
            academic_year=data.academic_year,
            subject_id=data.subject_id,
        )
        saved = await self.repo.create_user_group(ug)
        return UserGroupResponse(
            id=saved.id, user_id=saved.user_id,
            user_name=f"{user.first_name} {user.last_name}",
            group_id=saved.group_id, academic_year=saved.academic_year,
            subject_id=saved.subject_id, subject_name=subject_name,
        )

    async def list_teacher_assignments(self, institution_id: UUID) -> list[UserGroupResponse]:
        return [
            UserGroupResponse(
                id=ug.id, user_id=ug.user_id, user_name=name,
                group_id=ug.group_id, academic_year=ug.academic_year,
                subject_id=ug.subject_id, subject_name=subject_name,
            )
            for ug, name, subject_name in await self.repo.list_user_groups(institution_id)
        ]
