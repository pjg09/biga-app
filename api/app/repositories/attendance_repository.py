from dataclasses import dataclass
from datetime import date as PyDate, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.models.attendance import AttendanceJustification, AttendanceRecord, AttendanceToken
from app.models.class_period import ClassPeriod
from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user_group import UserGroup


@dataclass
class ScheduleRow:
    class_period: ClassPeriod
    group_name: str
    grade_name: str


@dataclass
class JustificationRow:
    record_id: UUID
    student_name: str
    group_name: str | None
    grade_name: str | None
    date: object
    reason: str
    submitted_at: object
    photo_url: str | None


@dataclass
class DayClassRow:
    class_period: ClassPeriod
    group_id: UUID
    group_name: str
    grade_name: str


@dataclass
class AttendanceContext:
    record: AttendanceRecord
    student: Student
    group_name: str | None
    grade_name: str | None


class AttendanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_teacher_classes_for_day(
        self,
        user_id: UUID,
        institution_id: UUID,
        academic_year: int,
        day_of_week: int,
    ) -> list[DayClassRow]:
        """Todas las clases (cualquier period_order) del docente para el día dado."""
        result = await self.session.execute(
            select(ClassPeriod, Group.id, Group.name, Grade.name)
            .join(UserGroup, UserGroup.group_id == ClassPeriod.group_id)
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
                ClassPeriod.institution_id == institution_id,
                ClassPeriod.day_of_week == day_of_week,
            )
            .order_by(ClassPeriod.start_time, ClassPeriod.period_order)
        )
        return [
            DayClassRow(class_period=row[0], group_id=row[1], group_name=row[2], grade_name=row[3])
            for row in result.all()
        ]

    async def get_teacher_class(
        self,
        user_id: UUID,
        class_period_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> DayClassRow | None:
        """Una clase específica que el docente dicta, con nombres de grupo/grado."""
        result = await self.session.execute(
            select(ClassPeriod, Group.id, Group.name, Grade.name)
            .join(UserGroup, UserGroup.group_id == ClassPeriod.group_id)
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                ClassPeriod.id == class_period_id,
                ClassPeriod.institution_id == institution_id,
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
            )
            .limit(1)
        )
        row = result.first()
        if not row:
            return None
        return DayClassRow(class_period=row[0], group_id=row[1], group_name=row[2], grade_name=row[3])

    async def get_taken_class_period_ids(
        self,
        class_period_ids: list[UUID],
        institution_id: UUID,
        date: PyDate,
    ) -> set[UUID]:
        """De los class_period_ids dados, cuáles ya tienen asistencia registrada hoy."""
        if not class_period_ids:
            return set()
        result = await self.session.execute(
            select(AttendanceRecord.class_period_id)
            .where(
                AttendanceRecord.class_period_id.in_(class_period_ids),
                AttendanceRecord.institution_id == institution_id,
                AttendanceRecord.date == date,
            )
            .distinct()
        )
        return set(result.scalars().all())

    async def teacher_owns_class_period(
        self,
        user_id: UUID,
        class_period_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> ClassPeriod | None:
        result = await self.session.execute(
            select(ClassPeriod)
            .join(UserGroup, UserGroup.group_id == ClassPeriod.group_id)
            .where(
                ClassPeriod.id == class_period_id,
                ClassPeriod.institution_id == institution_id,
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def get_group_roster(
        self,
        group_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> list[Student]:
        result = await self.session.execute(
            select(Student)
            .join(StudentGroup, StudentGroup.student_id == Student.id)
            .where(
                StudentGroup.group_id == group_id,
                StudentGroup.academic_year == academic_year,
                StudentGroup.is_active == True,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().all())

    async def get_records_for_class(
        self,
        class_period_id: UUID,
        institution_id: UUID,
        date: PyDate,
    ) -> list[AttendanceRecord]:
        result = await self.session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_period_id == class_period_id,
                AttendanceRecord.institution_id == institution_id,
                AttendanceRecord.date == date,
            )
        )
        return list(result.scalars().all())

    async def add_record(self, record: AttendanceRecord) -> AttendanceRecord:
        self.session.add(record)
        return record

    async def flush(self) -> None:
        await self.session.flush()

    async def get_record(self, record_id: UUID, institution_id: UUID) -> AttendanceRecord | None:
        result = await self.session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.id == record_id,
                AttendanceRecord.institution_id == institution_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(self, record: AttendanceRecord, status) -> AttendanceRecord:
        record.status = status
        await self.session.flush()
        return record

    # --- Contexto / tokens / justificación (usado por job y flujo público) ---

    async def get_context(self, record_id: UUID) -> AttendanceContext | None:
        result = await self.session.execute(
            select(AttendanceRecord, Student, Group.name, Grade.name)
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(Group, Group.id == AttendanceRecord.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(AttendanceRecord.id == record_id)
        )
        row = result.first()
        if not row:
            return None
        return AttendanceContext(record=row[0], student=row[1], group_name=row[2], grade_name=row[3])

    async def get_token_by_record(self, record_id: UUID) -> AttendanceToken | None:
        result = await self.session.execute(
            select(AttendanceToken).where(AttendanceToken.attendance_record_id == record_id)
        )
        return result.scalar_one_or_none()

    async def create_token(
        self,
        token_id: UUID,
        record_id: UUID,
        token: UUID,
        expires_at: datetime,
    ) -> AttendanceToken:
        obj = AttendanceToken(
            id=token_id,
            attendance_record_id=record_id,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_token_by_value(self, token: UUID) -> AttendanceToken | None:
        result = await self.session.execute(
            select(AttendanceToken).where(AttendanceToken.token == token)
        )
        return result.scalar_one_or_none()

    async def get_record_by_id(self, record_id: UUID) -> AttendanceRecord | None:
        # Sin filtro de institución: el flujo público de justificación se
        # autoriza con el token (UUID no adivinable), no con un JWT.
        result = await self.session.execute(
            select(AttendanceRecord).where(AttendanceRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    async def mark_token_used(self, token: AttendanceToken, used_at: datetime) -> None:
        token.used_at = used_at
        await self.session.flush()

    async def create_justification(
        self,
        justification_id: UUID,
        record_id: UUID,
        token_id: UUID,
        reason: str,
    ) -> AttendanceJustification:
        obj = AttendanceJustification(
            id=justification_id,
            attendance_record_id=record_id,
            token_id=token_id,
            reason=reason,
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    # --- Horario y mensajes (excusas) ---

    async def get_teacher_schedule(
        self,
        user_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> list[ScheduleRow]:
        result = await self.session.execute(
            select(ClassPeriod, Group.name, Grade.name)
            .join(UserGroup, UserGroup.group_id == ClassPeriod.group_id)
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
                ClassPeriod.institution_id == institution_id,
            )
            .order_by(ClassPeriod.day_of_week, ClassPeriod.start_time)
        )
        return [ScheduleRow(class_period=row[0], group_name=row[1], grade_name=row[2]) for row in result.all()]

    async def list_justifications_for_teacher(
        self,
        user_id: UUID,
        institution_id: UUID,
    ) -> list[JustificationRow]:
        result = await self.session.execute(
            select(
                AttendanceRecord.id,
                func.concat(Student.first_name, " ", Student.last_name),
                Group.name,
                Grade.name,
                AttendanceRecord.date,
                AttendanceJustification.reason,
                AttendanceJustification.submitted_at,
                Student.photo_url,
            )
            .join(AttendanceRecord, AttendanceRecord.id == AttendanceJustification.attendance_record_id)
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(Group, Group.id == AttendanceRecord.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                AttendanceRecord.institution_id == institution_id,
                AttendanceRecord.recorded_by_user_id == user_id,
            )
            .order_by(AttendanceJustification.submitted_at.desc())
        )
        return [
            JustificationRow(
                record_id=row[0],
                student_name=row[1],
                group_name=row[2],
                grade_name=row[3],
                date=row[4],
                reason=row[5],
                submitted_at=row[6],
                photo_url=row[7],
            )
            for row in result.all()
        ]
