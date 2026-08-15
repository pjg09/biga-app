from dataclasses import dataclass
from datetime import date as PyDate, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.models.attendance import (
    AttendanceAbsenceNote,
    AttendanceJustification,
    AttendanceJustificationNote,
    AttendanceRecord,
    AttendanceToken,
)
from app.models.class_period import ClassPeriod
from app.models.enums import AttendanceStatus
from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user import User


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
    attachment_key: str | None
    attachment_filename: str | None
    attachment_content_type: str | None
    justification_id: UUID
    student_id: UUID
    note_count: int
    archived: bool


@dataclass
class AbsenceRow:
    record_id: UUID
    student_id: UUID
    student_name: str
    photo_url: str | None
    grade_name: str | None
    group_name: str | None
    date: object
    period_name: str
    start_time: object
    end_time: object
    recorded_at: object
    status: object
    note_count: int
    guardian_notified: bool
    closed: bool


@dataclass
class JustificationDetailRow:
    justification: object
    record_id: UUID
    date: object
    student_id: UUID
    student_name: str
    photo_url: str | None
    group_name: str | None
    grade_name: str | None


@dataclass
class JustificationNoteRow:
    id: UUID
    note: str
    author_name: str
    created_at: object


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
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                # El docente del BLOQUE, no del salón: ver migración d6c1f8a390b4.
                ClassPeriod.user_id == user_id,
                # `class_periods` no tiene año; lo aporta su salón. Sin esto, un
                # bloque de un salón de 2025 seguiría apareciendo en 2026.
                Group.academic_year == academic_year,
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
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                ClassPeriod.id == class_period_id,
                ClassPeriod.institution_id == institution_id,
                # El docente del BLOQUE, no del salón: ver migración d6c1f8a390b4.
                ClassPeriod.user_id == user_id,
                # `class_periods` no tiene año; lo aporta su salón. Sin esto, un
                # bloque de un salón de 2025 seguiría apareciendo en 2026.
                Group.academic_year == academic_year,
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
            .join(Group, Group.id == ClassPeriod.group_id)
            .where(
                ClassPeriod.id == class_period_id,
                ClassPeriod.institution_id == institution_id,
                # El docente del BLOQUE, no del salón: ver migración d6c1f8a390b4.
                ClassPeriod.user_id == user_id,
                # `class_periods` no tiene año; lo aporta su salón. Sin esto, un
                # bloque de un salón de 2025 seguiría apareciendo en 2026.
                Group.academic_year == academic_year,
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
        attachment_key: str | None = None,
        attachment_filename: str | None = None,
        attachment_content_type: str | None = None,
        attachment_size_bytes: int | None = None,
    ) -> AttendanceJustification:
        obj = AttendanceJustification(
            id=justification_id,
            attendance_record_id=record_id,
            token_id=token_id,
            reason=reason,
            attachment_key=attachment_key,
            attachment_filename=attachment_filename,
            attachment_content_type=attachment_content_type,
            attachment_size_bytes=attachment_size_bytes,
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
            .join(Group, Group.id == ClassPeriod.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                # El docente del BLOQUE, no del salón: ver migración d6c1f8a390b4.
                ClassPeriod.user_id == user_id,
                # `class_periods` no tiene año; lo aporta su salón. Sin esto, un
                # bloque de un salón de 2025 seguiría apareciendo en 2026.
                Group.academic_year == academic_year,
                ClassPeriod.institution_id == institution_id,
            )
            .order_by(ClassPeriod.day_of_week, ClassPeriod.start_time)
        )
        return [ScheduleRow(class_period=row[0], group_name=row[1], grade_name=row[2]) for row in result.all()]

    async def list_justifications_for_teacher(
        self,
        user_id: UUID,
        institution_id: UUID,
        student_id: UUID | None = None,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[JustificationRow]:
        """Excusas dirigidas al docente que reportó la inasistencia.

        El conteo de notas va como subconsulta escalar y no como JOIN + GROUP BY:
        con el join habría que agrupar por todas las columnas seleccionadas, y
        cualquier columna nueva que se añada al SELECT rompería el GROUP BY en
        silencio.
        """
        note_count = (
            select(func.count(AttendanceJustificationNote.id))
            .where(AttendanceJustificationNote.justification_id == AttendanceJustification.id)
            .correlate(AttendanceJustification)
            .scalar_subquery()
        )

        stmt = (
            select(
                AttendanceRecord.id,
                func.concat(Student.first_name, " ", Student.last_name),
                Group.name,
                Grade.name,
                AttendanceRecord.date,
                AttendanceJustification.reason,
                AttendanceJustification.submitted_at,
                Student.photo_url,
                AttendanceJustification.attachment_key,
                AttendanceJustification.attachment_filename,
                AttendanceJustification.attachment_content_type,
                AttendanceJustification.id,
                Student.id,
                note_count,
                AttendanceJustification.archived_at,
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
            .offset(skip)
            .limit(limit)
        )
        if student_id:
            stmt = stmt.where(AttendanceRecord.student_id == student_id)
        if not include_archived:
            stmt = stmt.where(AttendanceJustification.archived_at.is_(None))

        result = await self.session.execute(stmt)
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
                attachment_key=row[8],
                attachment_filename=row[9],
                attachment_content_type=row[10],
                justification_id=row[11],
                student_id=row[12],
                note_count=row[13],
                archived=row[14] is not None,
            )
            for row in result.all()
        ]

    # --- Detalle, notas y cierre de un caso de Mensajes ---

    async def get_justification(
        self, justification_id: UUID, institution_id: UUID
    ) -> AttendanceJustification | None:
        """La justificación, validando que pertenece a la institución.

        El tenant se comprueba por el registro de asistencia:
        `attendance_justifications` no denormaliza `institution_id`.
        """
        result = await self.session.execute(
            select(AttendanceJustification)
            .join(AttendanceRecord, AttendanceRecord.id == AttendanceJustification.attendance_record_id)
            .where(
                AttendanceJustification.id == justification_id,
                AttendanceRecord.institution_id == institution_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_justification_detail(
        self, justification_id: UUID, institution_id: UUID
    ) -> JustificationDetailRow | None:
        result = await self.session.execute(
            select(
                AttendanceJustification,
                AttendanceRecord.id,
                AttendanceRecord.date,
                Student.id,
                func.concat(Student.first_name, " ", Student.last_name),
                Student.photo_url,
                Group.name,
                Grade.name,
            )
            .join(AttendanceRecord, AttendanceRecord.id == AttendanceJustification.attendance_record_id)
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(Group, Group.id == AttendanceRecord.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                AttendanceJustification.id == justification_id,
                AttendanceRecord.institution_id == institution_id,
            )
        )
        row = result.first()
        if not row:
            return None
        return JustificationDetailRow(
            justification=row[0],
            record_id=row[1],
            date=row[2],
            student_id=row[3],
            student_name=row[4],
            photo_url=row[5],
            group_name=row[6],
            grade_name=row[7],
        )

    async def list_justification_notes(self, justification_id: UUID) -> list[JustificationNoteRow]:
        result = await self.session.execute(
            select(
                AttendanceJustificationNote.id,
                AttendanceJustificationNote.note,
                func.concat(User.first_name, " ", User.last_name),
                AttendanceJustificationNote.created_at,
            )
            .join(User, User.id == AttendanceJustificationNote.author_user_id)
            .where(AttendanceJustificationNote.justification_id == justification_id)
            .order_by(AttendanceJustificationNote.created_at.asc())
        )
        return [
            JustificationNoteRow(id=r[0], note=r[1], author_name=r[2], created_at=r[3])
            for r in result.all()
        ]

    async def add_justification_note(
        self,
        note_id: UUID,
        justification_id: UUID,
        institution_id: UUID,
        author_user_id: UUID,
        note: str,
    ) -> AttendanceJustificationNote:
        obj = AttendanceJustificationNote(
            id=note_id,
            justification_id=justification_id,
            institution_id=institution_id,
            author_user_id=author_user_id,
            note=note,
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def set_justification_archived(
        self, justification: AttendanceJustification, archived_at: datetime | None
    ) -> None:
        justification.archived_at = archived_at
        await self.session.flush()

    # --- Inasistencias de primera hora sin justificar ---

    def _unjustified_absence_base(self, user_id: UUID, institution_id: UUID):
        """Criterio único de la sección, compartido por listado y detalle.

        Sale de aquí en cuanto **existe** una justificación, no cuando el estado
        pasa a JUSTIFIED: es la existencia del descargo lo que mueve el caso a
        Mensajes. `LATE` queda fuera a propósito — el estudiante sí llegó.
        """
        sin_justificar = ~select(AttendanceJustification.id).where(
            AttendanceJustification.attendance_record_id == AttendanceRecord.id
        ).exists()

        return (
            select(
                AttendanceRecord.id,
                Student.id,
                func.concat(Student.first_name, " ", Student.last_name),
                Student.photo_url,
                Grade.name,
                Group.name,
                AttendanceRecord.date,
                ClassPeriod.name,
                ClassPeriod.start_time,
                ClassPeriod.end_time,
                AttendanceRecord.created_at,
                AttendanceRecord.status,
                select(func.count(AttendanceAbsenceNote.id))
                .where(AttendanceAbsenceNote.attendance_record_id == AttendanceRecord.id)
                .correlate(AttendanceRecord)
                .scalar_subquery(),
                select(AttendanceToken.id)
                .where(AttendanceToken.attendance_record_id == AttendanceRecord.id)
                .correlate(AttendanceRecord)
                .exists(),
                AttendanceRecord.absence_closed_at,
            )
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(ClassPeriod, ClassPeriod.id == AttendanceRecord.class_period_id)
            .join(Group, Group.id == AttendanceRecord.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .where(
                AttendanceRecord.institution_id == institution_id,
                AttendanceRecord.recorded_by_user_id == user_id,
                ClassPeriod.period_order == 1,
                AttendanceRecord.status == AttendanceStatus.ABSENT,
                sin_justificar,
            )
        )

    @staticmethod
    def _to_absence_row(row) -> AbsenceRow:
        return AbsenceRow(
            record_id=row[0], student_id=row[1], student_name=row[2], photo_url=row[3],
            grade_name=row[4], group_name=row[5], date=row[6], period_name=row[7],
            start_time=row[8], end_time=row[9], recorded_at=row[10], status=row[11],
            note_count=row[12], guardian_notified=row[13],
            closed=row[14] is not None,
        )

    async def list_unjustified_absences(
        self,
        user_id: UUID,
        institution_id: UUID,
        student_id: UUID | None = None,
        include_closed: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AbsenceRow]:
        stmt = self._unjustified_absence_base(user_id, institution_id)
        if not include_closed:
            stmt = stmt.where(AttendanceRecord.absence_closed_at.is_(None))
        if student_id:
            stmt = stmt.where(AttendanceRecord.student_id == student_id)
        stmt = stmt.order_by(AttendanceRecord.date.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [self._to_absence_row(r) for r in result.all()]

    async def get_unjustified_absence(
        self, record_id: UUID, user_id: UUID, institution_id: UUID
    ) -> AbsenceRow | None:
        stmt = self._unjustified_absence_base(user_id, institution_id).where(
            AttendanceRecord.id == record_id
        )
        row = (await self.session.execute(stmt)).first()
        return self._to_absence_row(row) if row else None

    async def list_absence_notes(self, record_id: UUID) -> list[JustificationNoteRow]:
        result = await self.session.execute(
            select(
                AttendanceAbsenceNote.id,
                AttendanceAbsenceNote.note,
                func.concat(User.first_name, " ", User.last_name),
                AttendanceAbsenceNote.created_at,
            )
            .join(User, User.id == AttendanceAbsenceNote.author_user_id)
            .where(AttendanceAbsenceNote.attendance_record_id == record_id)
            .order_by(AttendanceAbsenceNote.created_at.asc())
        )
        return [
            JustificationNoteRow(id=r[0], note=r[1], author_name=r[2], created_at=r[3])
            for r in result.all()
        ]

    async def add_absence_note(
        self,
        note_id: UUID,
        record_id: UUID,
        institution_id: UUID,
        author_user_id: UUID,
        note: str,
    ) -> AttendanceAbsenceNote:
        obj = AttendanceAbsenceNote(
            id=note_id,
            attendance_record_id=record_id,
            institution_id=institution_id,
            author_user_id=author_user_id,
            note=note,
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def set_absence_closed(self, record_id: UUID, closed_at: datetime | None) -> None:
        record = await self.session.get(AttendanceRecord, record_id)
        if record is None:
            return
        record.absence_closed_at = closed_at
        await self.session.flush()
