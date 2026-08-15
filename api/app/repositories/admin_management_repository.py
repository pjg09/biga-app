from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.class_period import ClassPeriod
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

    async def get_class_period_by_unique(
        self, group_id: UUID, period_order: int, day_of_week: int
    ) -> ClassPeriod | None:
        result = await self.session.execute(
            select(ClassPeriod).where(
                ClassPeriod.group_id == group_id,
                ClassPeriod.period_order == period_order,
                ClassPeriod.day_of_week == day_of_week,
            )
        )
        return result.scalar_one_or_none()

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
            .order_by(ClassPeriod.day_of_week, ClassPeriod.period_order)
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
        self, group_id: UUID, day_of_week: int, start_order: int, span: int,
        exclude_id: UUID | None = None,
    ) -> ClassPeriod | None:
        """Bloque de ese salón y día cuyo rango de periodos choca con el dado.

        Duplica el EXCLUDE de la BD (migración `e9a3b7c2d418`) para poder dar un
        409 con mensaje en vez de dejar que reviente la constraint. Rangos
        semiabiertos: [a, a+span) se solapa con [b, b+span_b) si a < b+span_b y
        b < a+span.
        """
        end_order = start_order + span
        stmt = select(ClassPeriod).where(
            ClassPeriod.group_id == group_id,
            ClassPeriod.day_of_week == day_of_week,
            ClassPeriod.period_order < end_order,
            ClassPeriod.period_order + ClassPeriod.span > start_order,
        )
        if exclude_id:
            stmt = stmt.where(ClassPeriod.id != exclude_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def existing_period_slots(self, group_id: UUID) -> set[tuple[int, int]]:
        """(period_order, day_of_week) ya ocupados en ese salón.

        Se lee de una vez para que la creación masiva omita los existentes sin
        hacer una consulta por bloque.
        """
        result = await self.session.execute(
            select(ClassPeriod.period_order, ClassPeriod.day_of_week, ClassPeriod.span)
            .where(ClassPeriod.group_id == group_id)
        )
        # Una clase doble ocupa DOS órdenes: si solo se registrara el de inicio,
        # la creación masiva intentaría crear un bloque en el que ella cubre.
        ocupados = set()
        for order, day, span in result.all():
            for o in range(order, order + span):
                ocupados.add((o, day))
        return ocupados

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
