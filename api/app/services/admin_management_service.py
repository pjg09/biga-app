from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from datetime import datetime as PyDatetime

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.config import settings
from app.core.photos import ALLOWED_PHOTO_TYPES, resolve_photo_url
from app.core.security import compute_enrollment_hash, generate_temp_password, hash_password
from app.models.class_period import ClassPeriod
from app.models.enums import UserRole
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
    ClassPeriodBulkCreate,
    ClassPeriodBulkResult,
    ClassPeriodCreate,
    ClassPeriodUpdate,
    ClassPeriodResponse,
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


def _overlap_msg(otro) -> str:
    ocupa = (
        f"el orden {otro.period_order}"
        if otro.span == 1
        else f"los órdenes {otro.period_order} a {otro.period_order + otro.span - 1}"
    )
    return f"Ese rango de horas choca con «{otro.name}», que ocupa {ocupa} ese día"


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

    def _user_response(self, user: User) -> AdminUserResponse:
        resp = AdminUserResponse.model_validate(user)
        resp.photo_url = resolve_photo_url(self.storage, user.photo_url)
        return resp

    async def create_user(self, data: AdminUserCreate, institution_id: UUID) -> AdminUserResponse:
        if await self.repo.get_user_by_email(data.email.lower().strip()):
            raise _conflict("Ya existe un usuario con ese correo")
        document_number = data.document_number.strip()
        if await self.repo.get_user_by_document(institution_id, document_number):
            raise _conflict("Ya existe un usuario con este documento en la institución")

        # El admin nunca elige la contraseña: se genera una temporal y se le
        # manda al interesado por correo. Solo se persiste el bcrypt; la versión
        # en claro vive lo que dura este método y el mensaje encolado.
        temp_password = generate_temp_password()
        email = data.email.lower().strip()
        user = User(
            id=uuid4(),
            institution_id=institution_id,
            document_number=document_number,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=email,
            hashed_password=hash_password(temp_password),
            role=data.role,
            is_active=True,
        )
        saved = await self.repo.create_user(user)

        # Import local: a nivel de módulo, `app.jobs` importa Celery y este
        # service se importa desde el router en el arranque de la API.
        from app.jobs.auth_jobs import notify_staff_welcome

        # countdown corto por lo mismo que el OTP: si el request acabara
        # revirtiendo, el correo habría anunciado una cuenta que no existe.
        # `argsrepr` evita que la contraseña temporal caiga en los logs del worker.
        notify_staff_welcome.apply_async(
            (email, saved.first_name, temp_password, saved.role.value, f"{settings.frontend_url}/login"),
            countdown=2,
            argsrepr="('<correo>', '<nombre>', '<clave oculta>', '<rol>', '<url>')",
        )
        return self._user_response(saved)

    async def list_users(
        self, institution_id: UUID, include_inactive: bool = False
    ) -> list[AdminUserResponse]:
        return [
            self._user_response(u)
            for u in await self.repo.list_users(institution_id, include_inactive=include_inactive)
        ]

    async def set_user_active(
        self, user_id: UUID, institution_id: UUID, active: bool, current_user_id: UUID
    ) -> AdminUserResponse:
        """Baja lógica (y alta) de un miembro del personal.

        No se borra nada: solo se apaga `is_active`. Los registros que el usuario
        firmó (convivencia, asistencia, entregas del PAE) siguen apuntando a su
        fila y el histórico queda intacto.

        El acceso se revoca al instante y no al expirar el JWT: `get_current_user`
        comprueba `is_active` en cada request, así que un token todavía válido
        deja de servir en cuanto esto se guarda.
        """
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")

        if not active:
            # Desactivarse a uno mismo es un autobloqueo inmediato: el siguiente
            # request del propio admin ya fallaría en get_current_user.
            if user_id == current_user_id:
                raise _conflict("No puedes desactivar tu propia cuenta")
            # Y sin ningún admin activo, nadie podría volver a entrar a la
            # consola para revertirlo — ni siquiera para reactivar a este.
            if user.role == UserRole.ADMIN:
                if await self.repo.count_active_admins(institution_id, exclude_user_id=user_id) == 0:
                    raise _conflict(
                        "No puedes desactivar al único administrador activo de la institución"
                    )
            # Un bloque siempre tiene docente (NOT NULL), pero si ese docente
            # queda inactivo el bloque se queda sin nadie que tome lista — y en
            # primera hora, sin notificación al acudiente. Se obliga a reasignar
            # antes de dar de baja.
            bloques = await self.repo.count_periods_of_teacher(user_id)
            if bloques:
                raise _conflict(
                    f"{user.first_name} dicta {bloques} bloques del horario. "
                    "Reasígnalos a otro docente en Horarios › Rejilla semanal antes de eliminarlo."
                )

        user.is_active = active
        await self.repo.save_user(user)
        return self._user_response(user)

    async def get_user_detail(self, user_id: UUID, institution_id: UUID) -> AdminUserResponse:
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")
        return self._user_response(user)

    async def update_user(
        self, user_id: UUID, data: AdminUserUpdate, institution_id: UUID, current_user_id: UUID
    ) -> AdminUserResponse:
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")

        # Misma guarda que `set_user_active`, por la otra puerta: bajarse el
        # propio rol es el mismo autobloqueo que desactivarse. `require_admin`
        # rechazaría el siguiente request y, si era el único ADMIN, la
        # institución se queda sin acceso a la consola — solo recuperable con un
        # UPDATE manual en Postgres.
        if user_id == current_user_id and user.role == UserRole.ADMIN and data.role != UserRole.ADMIN:
            raise _conflict(
                "No puedes quitarte a ti mismo el rol de administrador. "
                "Pídeselo a otro administrador."
            )

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
        # La contraseña no se toca acá a propósito: el admin no puede fijar la de
        # otra persona. Para cambiarla está `/auth/password-reset`, que exige
        # acceso al correo del titular.
        await self.repo.save_user(user)
        return self._user_response(user)

    async def set_user_photo(
        self, user_id: UUID, institution_id: UUID, data: bytes, content_type: str
    ) -> AdminUserResponse:
        """Sube la foto del miembro del personal al bucket y guarda su key.

        Mismo contrato que `StudentService.set_photo`, con dos diferencias: el
        prefijo es `staff-photos/` (no se mezcla con las fotos de estudiantes,
        que sí alimentan la identificación del PAE) y el aislamiento multi-tenant
        lo da `get_user`, que ya filtra por `institution_id`.
        """
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
        user = await self.repo.get_user(user_id, institution_id)
        if not user:
            raise _not_found("Usuario no encontrado en esta institución")

        key = f"staff-photos/{institution_id}/{user_id}.{ext}"
        self.storage.upload(key, data, content_type)
        user.photo_url = key
        await self.repo.save_user(user)
        return self._user_response(user)

    # --- Grados ---

    async def list_grades(self, institution_id: UUID) -> list[GradeResponse]:
        return [GradeResponse.model_validate(g) for g in await self.repo.list_grades(institution_id)]

    # --- Materias (catálogo) ---

    async def create_subject(self, data: SubjectCreate, institution_id: UUID) -> SubjectResponse:
        if await self.repo.get_subject_by_name(institution_id, data.name):
            raise _conflict("Ya existe una materia con ese nombre")
        subject = Subject(id=uuid4(), institution_id=institution_id, name=data.name)
        return SubjectResponse.model_validate(await self.repo.create_subject(subject))

    async def rename_subject(
        self, subject_id: UUID, name: str, institution_id: UUID
    ) -> SubjectResponse:
        """Renombra la materia del catálogo.

        Solo cambia la etiqueta: `subject_id` no se toca, así que las
        asignaciones docente-salón (`user_groups.subject_id`) siguen apuntando a
        la misma fila y el filtro "Mis estudiantes por materia" no se entera.
        """
        subject = await self.repo.get_subject(subject_id, institution_id)
        if not subject:
            raise _not_found("Materia no encontrada en esta institución")

        # Chequeo previo sobre UNIQUE(institution_id, name), excluyéndose a sí
        # misma para que renombrar a su propio nombre no dé falso conflicto.
        existing = await self.repo.get_subject_by_name(institution_id, name)
        if existing and existing.id != subject.id:
            raise _conflict("Ya existe una materia con ese nombre")

        subject.name = name
        await self.repo.save_subject(subject)
        return SubjectResponse.model_validate(subject)

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
                id=g.id, grade_id=g.grade_id, grade_name=grade_name, grade_level=grade_level,
                name=g.name, academic_year=g.academic_year, student_count=count,
            )
            for g, grade_name, grade_level, count in await self.repo.list_groups(institution_id)
        ]

    async def rename_group(
        self, group_id: UUID, name: str, institution_id: UUID
    ) -> GroupResponse:
        """Cambia solo el nombre del salón. No toca grado ni año, así que las
        matrículas, horarios y asignaciones docentes siguen apuntando al mismo
        `group_id` y nada más se entera del cambio."""
        group = await self.repo.get_group(group_id, institution_id)
        if not group:
            raise _not_found("Salón no encontrado en esta institución")

        # `name` ya llega recortado y no vacío desde `GroupUpdate`.
        # Chequeo previo por la constraint UNIQUE(grade_id, name, academic_year),
        # para dar un mensaje claro en vez de dejar que reviente la BD.
        existing = await self.repo.get_group_by_unique(group.grade_id, name, group.academic_year)
        if existing and existing.id != group.id:
            raise _conflict(f"Ya existe un salón «{name}» en ese grado para {group.academic_year}")

        group.name = name
        await self.repo.save_group(group)

        grade = await self.repo.get_grade(group.grade_id, institution_id)
        return GroupResponse(
            id=group.id, grade_id=group.grade_id,
            grade_name=grade.name if grade else None,
            grade_level=grade.level if grade else None,
            name=group.name, academic_year=group.academic_year,
        )

    async def add_student_to_group(
        self, group_id: UUID, student_id: UUID, institution_id: UUID
    ) -> StudentGroupResponse:
        """Mete a un estudiante en un salón, moviéndolo si ya estaba en otro.

        `student_groups` tiene `UNIQUE(student_id, academic_year)`: un estudiante
        vive en un único salón por año. Así que "agregar" y "mover" son la misma
        operación — se reutiliza la fila del año en curso en vez de crear otra,
        que chocaría con la constraint. Mismo tratamiento que
        `update_student_full`, para que ambas puertas dejen los datos igual.
        """
        if not await self.repo.get_student(student_id, institution_id):
            raise _not_found("Estudiante no encontrado en esta institución")
        group = await self.repo.get_group(group_id, institution_id)
        if not group:
            raise _not_found("Salón no encontrado en esta institución")

        academic_year = date.today().year
        sg = await self.repo.get_student_group(student_id, academic_year)
        if sg:
            if sg.group_id == group.id and sg.is_active:
                raise _conflict("El estudiante ya está en este salón")
            sg.group_id = group.id
            sg.is_active = True
            await self.repo.save_student_group(sg)
        else:
            sg = await self.repo.create_student_group(
                StudentGroup(
                    id=uuid4(), student_id=student_id, group_id=group.id,
                    academic_year=academic_year, is_active=True,
                )
            )
        return StudentGroupResponse.model_validate(sg)

    async def remove_student_from_group(
        self, group_id: UUID, student_id: UUID, institution_id: UUID
    ) -> None:
        """Saca a un estudiante del salón: `is_active = False`, sin borrar la fila.

        La matrícula es histórico — de ella cuelga en qué salón estuvo ese año.
        Se exige que la fila sea **de este salón** para que un `DELETE` con el
        salón equivocado no desmatricule a alguien de otro sitio.
        """
        if not await self.repo.get_group(group_id, institution_id):
            raise _not_found("Salón no encontrado en esta institución")
        if not await self.repo.get_student(student_id, institution_id):
            raise _not_found("Estudiante no encontrado en esta institución")

        sg = await self.repo.get_student_group_in_group(
            student_id, group_id, date.today().year
        )
        if not sg or not sg.is_active:
            raise _not_found("El estudiante no está matriculado en este salón")
        sg.is_active = False
        await self.repo.save_student_group(sg)

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

    async def set_student_active(
        self, student_id: UUID, institution_id: UUID, active: bool
    ) -> StudentResponse:
        """Baja lógica (y alta) de un estudiante.

        No se borra nada. Todo lo firmado o registrado a su nombre —
        agendatorio, asistencia, justificaciones, entregas del PAE — sigue en
        pie: los hashes del PAE se calculan sobre el `student_id`, que no cambia.

        Basta con apagar `is_active` para que desaparezca de toda la operación:
        listados, búsqueda, rosters de asistencia y del PAE ya filtran por esa
        columna. Las inscripciones al PAE **no** se tocan, porque sus consultas
        hacen join con `students` y ya lo excluyen.
        """
        student = await self.student_repo.get_by_id(student_id, institution_id, include_inactive=True)
        if not student:
            raise _not_found("Estudiante no encontrado")
        student.is_active = active
        await self.student_repo.save(student)
        return StudentResponse.model_validate(student)

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
        choque = await self.repo.find_overlapping_period(
            data.group_id, data.day_of_week, data.period_order, data.span
        )
        if choque:
            raise _conflict(_overlap_msg(choque))
        await self._check_period_refs(data, institution_id, data.group_id)
        cp = ClassPeriod(
            id=uuid4(),
            institution_id=institution_id,
            group_id=data.group_id,
            name=data.name,
            period_order=data.period_order,
            start_time=data.start_time,
            end_time=data.end_time,
            day_of_week=data.day_of_week,
            span=data.span,
            subject_id=data.subject_id,
            user_id=data.user_id,
        )
        await self.repo.create_class_period(cp)
        return await self._period_response(cp, institution_id)

    async def _check_period_refs(self, data, institution_id: UUID, group_id: UUID) -> None:
        """Valida materia y docente, y garantiza el vínculo docente–salón.

        La materia es opcional; el docente **no** (ver migración `d6c1f8a390b4`).
        Ambos deben existir en ESTA institución: sin el chequeo, un id de otro
        colegio pasaría la FK sin problema.

        Además crea la fila de `user_groups` si falta. Sin ella el docente vería
        la clase en "Mis clases de hoy" (que ahora filtra por bloque) pero no a
        sus estudiantes en "Mis estudiantes" (que sigue filtrando por salón).
        """
        if data.subject_id and not await self.repo.get_subject(data.subject_id, institution_id):
            raise _not_found("Materia no encontrada en esta institución")
        user = await self.repo.get_user(data.user_id, institution_id)
        if not user:
            raise _not_found("Docente no encontrado en esta institución")
        if not user.is_active:
            raise _conflict("Ese docente está desactivado: nadie tomaría lista en el bloque")

        year = date.today().year
        if not await self.repo.get_user_group(user.id, group_id, year):
            await self.repo.create_user_group(UserGroup(
                id=uuid4(), user_id=user.id, group_id=group_id, academic_year=year,
            ))

    async def _period_response(self, cp: ClassPeriod, institution_id: UUID) -> ClassPeriodResponse:
        resp = ClassPeriodResponse.model_validate(cp)
        if cp.subject_id:
            s = await self.repo.get_subject(cp.subject_id, institution_id)
            resp.subject_name = s.name if s else None
        if cp.user_id:
            u = await self.repo.get_user(cp.user_id, institution_id)
            resp.teacher_name = f"{u.first_name} {u.last_name}" if u else None
        return resp

    async def bulk_create_class_periods(
        self, data: ClassPeriodBulkCreate, institution_id: UUID
    ) -> ClassPeriodBulkResult:
        """Crea la jornada de un salón (periodos × días) en una sola petición.

        Omite los (orden, día) ya existentes en vez de fallar: así se puede
        volver a lanzar para rellenar huecos sin borrar lo que ya estaba, que es
        el caso real cuando a un horario se le añade un día o una hora más.
        """
        if not await self.repo.get_group(data.group_id, institution_id):
            raise _not_found("Salón no encontrado en esta institución")
        for p in data.periods:
            await self._check_period_refs(p, institution_id, data.group_id)

        ocupados = await self.repo.existing_period_slots(data.group_id)
        created = skipped = 0
        for day in data.days:
            for p in data.periods:
                if (p.period_order, day) in ocupados:
                    skipped += 1
                    continue
                await self.repo.create_class_period(ClassPeriod(
                    id=uuid4(), institution_id=institution_id, group_id=data.group_id,
                    name=p.name, period_order=p.period_order,
                    start_time=p.start_time, end_time=p.end_time, day_of_week=day,
                    span=p.span, subject_id=p.subject_id, user_id=p.user_id,
                ))
                created += 1
        return ClassPeriodBulkResult(created=created, skipped=skipped)

    async def update_class_period(
        self, cp_id: UUID, data: ClassPeriodUpdate, institution_id: UUID
    ) -> ClassPeriodResponse:
        cp = await self.repo.get_class_period(cp_id, institution_id)
        if not cp:
            raise _not_found("Bloque no encontrado en esta institución")
        await self._check_period_refs(data, institution_id, cp.group_id)

        # Orden y span pueden cambiar; ambos mueven el rango que ocupa el bloque.
        choque = await self.repo.find_overlapping_period(
            cp.group_id, cp.day_of_week, data.period_order, data.span, exclude_id=cp.id
        )
        if choque:
            raise _conflict(_overlap_msg(choque))

        cp.name = data.name
        cp.period_order = data.period_order
        cp.span = data.span
        cp.start_time = data.start_time
        cp.end_time = data.end_time
        cp.subject_id = data.subject_id
        cp.user_id = data.user_id
        await self.repo.save_class_period(cp)
        return await self._period_response(cp, institution_id)

    async def delete_class_period(self, cp_id: UUID, institution_id: UUID) -> None:
        """Borrado real, no baja lógica: un bloque horario no es histórico, es
        configuración. Los `attendance_records` que lo referencian sí lo son —
        por eso se rechaza si ya tiene asistencia tomada."""
        cp = await self.repo.get_class_period(cp_id, institution_id)
        if not cp:
            raise _not_found("Bloque no encontrado en esta institución")
        if await self.repo.count_attendance_for_period(cp_id) > 0:
            raise _conflict(
                "No se puede eliminar: ya se tomó asistencia en este bloque. "
                "Edítalo en vez de borrarlo."
            )
        await self.repo.delete_class_period(cp)

    async def list_class_periods(self, group_id: UUID, institution_id: UUID) -> list[ClassPeriodResponse]:
        if not await self.repo.get_group(group_id, institution_id):
            raise _not_found("Grupo no encontrado en esta institución")
        out = []
        for cp, subject_name, teacher_name in await self.repo.list_class_periods(group_id, institution_id):
            resp = ClassPeriodResponse.model_validate(cp)
            resp.subject_name = subject_name
            resp.teacher_name = teacher_name
            out.append(resp)
        return out

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
