from datetime import time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.class_period import ClassPeriod
from app.models.pae import PAEDelivery, PAEEnrollment
from app.models.enums import UserRole
from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.subject import Subject
from app.models.user import User
from app.models.user_group import UserGroup


class AdminManagementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _add(self, obj):
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    # --- Usuarios ---

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_document(self, institution_id: UUID, document_number: str) -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.institution_id == institution_id,
                User.document_number == document_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_user(self, user_id: UUID, institution_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        return await self._add(user)

    async def save_user(self, user: User) -> User:
        await self.session.flush()
        return user

    async def list_users(self, institution_id: UUID, include_inactive: bool = False) -> list[User]:
        stmt = (
            select(User)
            .where(User.institution_id == institution_id)
            .order_by(User.role, User.last_name, User.first_name)
        )
        if not include_inactive:
            stmt = stmt.where(User.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_admins(self, institution_id: UUID, exclude_user_id: UUID) -> int:
        """Administradores activos de la institución sin contar a `exclude_user_id`.

        Sirve para no dejar la consola sin ningún admin: si desactivar a alguien
        deja este contador en 0, nadie podría volver a entrar a reactivarlo.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.institution_id == institution_id,
                User.role == UserRole.ADMIN,
                User.is_active == True,  # noqa: E712
                User.id != exclude_user_id,
            )
        )
        return result.scalar_one()

    # --- Grados ---

    async def get_grade(self, grade_id: UUID, institution_id: UUID) -> Grade | None:
        result = await self.session.execute(
            select(Grade).where(Grade.id == grade_id, Grade.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def list_grades(self, institution_id: UUID) -> list[Grade]:
        result = await self.session.execute(
            select(Grade).where(Grade.institution_id == institution_id).order_by(Grade.level)
        )
        return list(result.scalars().all())

    # --- Materias (catálogo) ---

    async def get_subject(self, subject_id: UUID, institution_id: UUID) -> Subject | None:
        result = await self.session.execute(
            select(Subject).where(Subject.id == subject_id, Subject.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def get_subject_by_name(self, institution_id: UUID, name: str) -> Subject | None:
        result = await self.session.execute(
            select(Subject).where(Subject.institution_id == institution_id, Subject.name == name)
        )
        return result.scalar_one_or_none()

    async def create_subject(self, subject: Subject) -> Subject:
        return await self._add(subject)

    async def save_subject(self, subject: Subject) -> Subject:
        await self.session.flush()
        return subject

    async def list_subjects(self, institution_id: UUID) -> list[Subject]:
        result = await self.session.execute(
            select(Subject).where(Subject.institution_id == institution_id).order_by(Subject.name)
        )
        return list(result.scalars().all())

    # --- Grupos ---

    async def get_group(self, group_id: UUID, institution_id: UUID) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.id == group_id, Group.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def get_group_by_unique(self, grade_id: UUID, name: str, academic_year: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(
                Group.grade_id == grade_id,
                Group.name == name,
                Group.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_group(self, group: Group) -> Group:
        return await self._add(group)

    async def save_group(self, group: Group) -> Group:
        await self.session.flush()
        return group

    async def list_groups(self, institution_id: UUID) -> list[tuple[Group, str, int, int]]:
        """(grupo, nombre del grado, nivel del grado, nº de estudiantes activos).

        El conteo va como subquery correlacionada y no como `GROUP BY` sobre un
        join: con `GROUP BY` un salón vacío se perdería salvo LEFT JOIN, y la
        consola necesita ver justamente los salones vacíos para poder llenarlos.
        """
        student_count = (
            select(func.count())
            .select_from(StudentGroup)
            .join(Student, Student.id == StudentGroup.student_id)
            .where(
                StudentGroup.group_id == Group.id,
                StudentGroup.is_active == True,  # noqa: E712
                Student.is_active == True,  # noqa: E712
            )
            .correlate(Group)
            .scalar_subquery()
        )
        result = await self.session.execute(
            select(Group, Grade.name, Grade.level, student_count)
            .join(Grade, Grade.id == Group.grade_id)
            .where(Group.institution_id == institution_id)
            .order_by(Grade.level, Group.name)
        )
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def get_student_group_in_group(
        self, student_id: UUID, group_id: UUID, academic_year: int
    ) -> StudentGroup | None:
        result = await self.session.execute(
            select(StudentGroup).where(
                StudentGroup.student_id == student_id,
                StudentGroup.group_id == group_id,
                StudentGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    # --- Matrícula estudiante-grupo ---

    async def get_student(self, student_id: UUID, institution_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_student_group(self, student_id: UUID, academic_year: int) -> StudentGroup | None:
        result = await self.session.execute(
            select(StudentGroup).where(
                StudentGroup.student_id == student_id,
                StudentGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_student_group(self, sg: StudentGroup) -> StudentGroup:
        return await self._add(sg)

    async def save_student_group(self, sg: StudentGroup) -> StudentGroup:
        await self.session.flush()
        return sg

    # --- Horarios (class_periods) ---

    async def create_class_period(self, cp: ClassPeriod) -> ClassPeriod:
        return await self._add(cp)

    async def list_class_periods(
        self, group_id: UUID, institution_id: UUID
    ) -> list[tuple[ClassPeriod, str | None, str | None]]:
        """(bloque, nombre de la materia, nombre del docente).

        LEFT JOIN en ambos: materia y docente son nullable — un horario a medio
        armar debe seguir listándose entero.
        """
        result = await self.session.execute(
            select(
                ClassPeriod,
                Subject.name,
                (User.first_name + " " + User.last_name).label("teacher_name"),
            )
            .outerjoin(Subject, Subject.id == ClassPeriod.subject_id)
            .outerjoin(User, User.id == ClassPeriod.user_id)
            .where(
                ClassPeriod.group_id == group_id,
                ClassPeriod.institution_id == institution_id,
            )
            .order_by(ClassPeriod.day_of_week, ClassPeriod.start_time)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_class_period(self, cp_id: UUID, institution_id: UUID) -> ClassPeriod | None:
        result = await self.session.execute(
            select(ClassPeriod).where(
                ClassPeriod.id == cp_id, ClassPeriod.institution_id == institution_id
            )
        )
        return result.scalar_one_or_none()

    async def save_class_period(self, cp: ClassPeriod) -> ClassPeriod:
        await self.session.flush()
        return cp

    async def delete_class_period(self, cp: ClassPeriod) -> None:
        await self.session.delete(cp)
        await self.session.flush()

    async def get_user_group(self, user_id: UUID, group_id: UUID, academic_year: int) -> UserGroup | None:
        result = await self.session.execute(
            select(UserGroup).where(
                UserGroup.user_id == user_id,
                UserGroup.group_id == group_id,
                UserGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def count_periods_of_teacher(self, user_id: UUID) -> int:
        """Bloques horarios que dicta ese docente. Si tiene alguno, desactivarlo
        dejaría esos bloques sin nadie que tome lista."""
        result = await self.session.execute(
            select(func.count()).select_from(ClassPeriod).where(ClassPeriod.user_id == user_id)
        )
        return result.scalar_one()

    async def count_attendance_for_period(self, cp_id: UUID) -> int:
        """Asistencias ya tomadas en ese bloque. Si hay alguna, el bloque no se
        puede borrar: `attendance_records.class_period_id` es FK y esos
        registros sí son histórico."""
        result = await self.session.execute(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(AttendanceRecord.class_period_id == cp_id)
        )
        return result.scalar_one()

    async def find_overlapping_period(
        self, group_id: UUID, day_of_week: int, start_time: time, end_time: time,
        exclude_id: UUID | None = None,
    ) -> ClassPeriod | None:
        """Bloque de ese salón y día que se pisa EN EL RELOJ con el rango dado.

        Duplica el EXCLUDE `class_periods_no_time_overlap` (migración
        `f2d5a81c9e37`) para poder dar un 409 con mensaje en vez de dejar que
        reviente la constraint. Rangos semiabiertos: [a1,a2) solapa con [b1,b2)
        si a1 < b2 y b1 < a2 — así dos clases seguidas (07:50 fin, 07:50
        inicio) NO cuentan como solape.
        """
        stmt = select(ClassPeriod).where(
            ClassPeriod.group_id == group_id,
            ClassPeriod.day_of_week == day_of_week,
            ClassPeriod.start_time < end_time,
            ClassPeriod.end_time > start_time,
        )
        if exclude_id:
            stmt = stmt.where(ClassPeriod.id != exclude_id)
        result = await self.session.execute(stmt.order_by(ClassPeriod.start_time).limit(1))
        return result.scalar_one_or_none()

    async def find_teacher_conflict(
        self, user_id: UUID, day_of_week: int, start_time: time, end_time: time,
        exclude_id: UUID | None = None,
    ) -> tuple[ClassPeriod, str, str] | None:
        """Bloque de OTRO salón donde ese docente ya está a esa hora.

        `find_overlapping_period` mira el salón; esta mira a la persona. Son dos
        invariantes distintos: un salón no puede tener dos clases a la vez, y un
        docente no puede estar en dos aulas a la vez. La segunda faltaba, y por
        eso el docente demo llegó a tener cuatro primeras horas simultáneas y
        cuatro clases pendientes de lista a las 10:00 en «Mis clases de hoy».

        Devuelve el bloque más el grado y salón, que es lo que hace legible el
        409 («ya dicta en Once A de 07:00 a 07:50»).
        """
        stmt = (
            select(ClassPeriod, Grade.name, Group.name)
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                ClassPeriod.user_id == user_id,
                ClassPeriod.day_of_week == day_of_week,
                ClassPeriod.start_time < end_time,
                ClassPeriod.end_time > start_time,
            )
        )
        if exclude_id:
            stmt = stmt.where(ClassPeriod.id != exclude_id)
        row = (await self.session.execute(stmt.order_by(ClassPeriod.start_time).limit(1))).first()
        return (row[0], row[1], row[2]) if row else None

    async def list_periods_of_day(self, group_id: UUID, day_of_week: int) -> list[ClassPeriod]:
        """Bloques de ese salón y día, en orden de reloj. Base de la
        renumeración de `period_order` (ver `_renumber_day` en el service)."""
        result = await self.session.execute(
            select(ClassPeriod)
            .where(ClassPeriod.group_id == group_id, ClassPeriod.day_of_week == day_of_week)
            .order_by(ClassPeriod.start_time)
        )
        return list(result.scalars().all())

    async def max_period_order(self, group_id: UUID, day_of_week: int) -> int:
        """Mayor `period_order` de ese salón y día, 0 si no hay bloques. Sirve
        para darle al bloque recién creado un orden provisional que no viole la
        UNIQUE antes de que `_renumber_day` reparta los definitivos."""
        result = await self.session.execute(
            select(func.max(ClassPeriod.period_order)).where(
                ClassPeriod.group_id == group_id, ClassPeriod.day_of_week == day_of_week
            )
        )
        return result.scalar_one() or 0

    async def flush(self) -> None:
        await self.session.flush()

    # --- PAE: listado de inscritos para la consola ---

    async def list_pae_enrollments(
        self, institution_id: UUID, academic_year: int, include_inactive: bool = False,
        group_id: UUID | None = None,
    ) -> list[dict]:
        """Inscritos al PAE con los datos del estudiante ya resueltos.

        Vive aquí y no en `PAERepository` porque es una consulta de la consola de
        gestión —joins con salón, grado y última entrega— y no una operación
        sobre la entidad `PAEEnrollment`; esas (crear, reactivar) siguen en
        `PAERepository`, que el service ya tiene inyectado.

        `LEFT JOIN` en salón y grado a propósito: un estudiante sin matrícula
        puede estar inscrito al PAE, y ocultarlo del listado dejaría raciones
        pedidas que nadie ve.
        """
        ultima = (
            select(PAEDelivery.student_id, func.max(PAEDelivery.delivery_date).label("ultima"))
            .where(PAEDelivery.institution_id == institution_id)
            .group_by(PAEDelivery.student_id)
            .subquery()
        )
        stmt = (
            select(
                PAEEnrollment.student_id, PAEEnrollment.academic_year,
                PAEEnrollment.enrolled_at, PAEEnrollment.is_active,
                Student.document_number, Student.first_name, Student.last_name,
                Student.photo_url, Student.is_active.label("student_is_active"),
                Grade.name.label("grade_name"), Group.name.label("group_name"),
                ultima.c.ultima.label("last_delivery"),
            )
            .join(Student, Student.id == PAEEnrollment.student_id)
            .outerjoin(StudentGroup, (StudentGroup.student_id == Student.id)
                       & (StudentGroup.is_active == True))
            .outerjoin(Group, (Group.id == StudentGroup.group_id)
                       & (Group.academic_year == academic_year))
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .outerjoin(ultima, ultima.c.student_id == Student.id)
            .where(
                PAEEnrollment.institution_id == institution_id,
                Student.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
            )
            .order_by(Student.last_name, Student.first_name)
        )
        if not include_inactive:
            stmt = stmt.where(PAEEnrollment.is_active == True)
        result = await self.session.execute(stmt)
        return [dict(r) for r in result.mappings().all()]

    async def count_pae_enrollments(
        self, institution_id: UUID, academic_year: int
    ) -> tuple[int, int]:
        """(activos, inactivos) del año. Se cuenta en BD y no sobre la lista ya
        filtrada: el contador debe ser el mismo aunque la vista esté filtrada."""
        result = await self.session.execute(
            select(PAEEnrollment.is_active, func.count())
            .where(
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
            )
            .group_by(PAEEnrollment.is_active)
        )
        conteo = {bool(row[0]): row[1] for row in result.all()}
        return conteo.get(True, 0), conteo.get(False, 0)

    # --- Asignación docente-grupo (user_groups) ---

    async def get_user_group(self, user_id: UUID, group_id: UUID, academic_year: int) -> UserGroup | None:
        result = await self.session.execute(
            select(UserGroup).where(
                UserGroup.user_id == user_id,
                UserGroup.group_id == group_id,
                UserGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_user_group(self, ug: UserGroup) -> UserGroup:
        return await self._add(ug)

    async def list_user_groups(self, institution_id: UUID) -> list[tuple[UserGroup, str, str | None]]:
        result = await self.session.execute(
            select(UserGroup, func.concat(User.first_name, " ", User.last_name), Subject.name)
            .join(User, User.id == UserGroup.user_id)
            .join(Group, Group.id == UserGroup.group_id)
            .outerjoin(Subject, Subject.id == UserGroup.subject_id)
            .where(Group.institution_id == institution_id)
            .order_by(UserGroup.academic_year.desc())
        )
        return [(row[0], row[1], row[2]) for row in result.all()]
