from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.config import settings
from app.core.photos import resolve_photo_url
from app.jobs.attendance_jobs import notify_absence_first_hour
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import (
    AttendanceRecordResponse,
    AttendanceStudentItem,
    AttendanceSubmit,
    ClassAttendanceResponse,
    ClassSlot,
    JustificationInfo,
    JustificationMessage,
    ScheduleItem,
    TodayClassesResponse,
)

_SUBMITTABLE = {AttendanceStatus.PRESENT, AttendanceStatus.ABSENT}


class AttendanceService:
    def __init__(self, repo: AttendanceRepository, storage: S3StorageAdapter):
        self.storage = storage
        self.repo = repo

    async def get_today_classes(self, user_id: UUID, institution_id: UUID) -> TodayClassesResponse:
        """Lista todas las clases del docente para hoy (para el selector de asistencia)."""
        today = date.today()
        academic_year = today.year
        day_of_week = today.isoweekday()  # 1 = lunes ... 7 = domingo

        # NOTA (tweak dev): originalmente `> 5` (Lun-Vie). Subido a `> 6` para
        # permitir sábado en pruebas. Revertir a `> 5` para volver al diseño Lun-Vie.
        if day_of_week > 6:
            return TodayClassesResponse(date=today, classes=[])

        rows = await self.repo.get_teacher_classes_for_day(
            user_id=user_id,
            institution_id=institution_id,
            academic_year=academic_year,
            day_of_week=day_of_week,
        )
        taken = await self.repo.get_taken_class_period_ids(
            class_period_ids=[r.class_period.id for r in rows],
            institution_id=institution_id,
            date=today,
        )
        return TodayClassesResponse(
            date=today,
            classes=[
                ClassSlot(
                    class_period_id=r.class_period.id,
                    period_order=r.class_period.period_order,
                    name=r.class_period.name,
                    group_id=r.group_id,
                    group_name=r.group_name,
                    grade_name=r.grade_name,
                    start_time=r.class_period.start_time,
                    end_time=r.class_period.end_time,
                    already_taken=r.class_period.id in taken,
                    is_first_hour=r.class_period.period_order == 1,
                )
                for r in rows
            ],
        )

    async def get_class_attendance(
        self,
        user_id: UUID,
        institution_id: UUID,
        class_period_id: UUID,
    ) -> ClassAttendanceResponse:
        """Roster + estado de asistencia de hoy para una clase específica del docente."""
        today = date.today()
        academic_year = today.year

        cls = await self.repo.get_teacher_class(
            user_id=user_id,
            class_period_id=class_period_id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La clase no existe o no está asignada a este docente",
            )

        roster = await self.repo.get_group_roster(
            group_id=cls.group_id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        existing = await self.repo.get_records_for_class(
            class_period_id=class_period_id,
            institution_id=institution_id,
            date=today,
        )
        status_by_student = {r.student_id: r.status for r in existing}
        record_by_student = {r.student_id: r.id for r in existing}

        return ClassAttendanceResponse(
            class_period_id=cls.class_period.id,
            group_id=cls.group_id,
            group_name=cls.group_name,
            grade_name=cls.grade_name,
            period_name=cls.class_period.name,
            period_order=cls.class_period.period_order,
            is_first_hour=cls.class_period.period_order == 1,
            start_time=cls.class_period.start_time,
            end_time=cls.class_period.end_time,
            date=today,
            already_taken=len(existing) > 0,
            students=[
                AttendanceStudentItem(
                    student_id=s.id,
                    document_number=s.document_number,
                    first_name=s.first_name,
                    last_name=s.last_name,
                    photo_url=resolve_photo_url(self.storage, s.photo_url),
                    status=status_by_student.get(s.id),
                    record_id=record_by_student.get(s.id),
                )
                for s in roster
            ],
        )

    async def submit_attendance(
        self,
        user_id: UUID,
        institution_id: UUID,
        data: AttendanceSubmit,
    ) -> list[AttendanceRecordResponse]:
        today = date.today()
        academic_year = today.year

        for entry in data.entries:
            if entry.status not in _SUBMITTABLE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Al tomar lista solo se permite PRESENT o ABSENT",
                )

        class_period = await self.repo.teacher_owns_class_period(
            user_id=user_id,
            class_period_id=data.class_period_id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        if not class_period:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La clase no existe o no está asignada a este docente",
            )

        existing = await self.repo.get_records_for_class(
            class_period_id=data.class_period_id,
            institution_id=institution_id,
            date=today,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La asistencia de esta clase ya fue registrada hoy",
            )

        roster = await self.repo.get_group_roster(
            group_id=class_period.group_id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        roster_ids = {s.id for s in roster}
        entry_ids = {e.student_id for e in data.entries}
        if entry_ids != roster_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Las entradas deben cubrir exactamente a los estudiantes del grupo",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        created: list[AttendanceRecord] = []
        for entry in data.entries:
            record = AttendanceRecord(
                id=uuid4(),
                student_id=entry.student_id,
                group_id=class_period.group_id,
                class_period_id=class_period.id,
                institution_id=institution_id,
                recorded_by_user_id=user_id,
                date=today,
                status=entry.status,
                created_at=now,
            )
            await self.repo.add_record(record)
            created.append(record)
        await self.repo.flush()

        # La notificación al acudiente solo aplica a la PRIMERA HORA (scope 3.2):
        # el resto de las clases se registran para historial, sin correo.
        # Se encola con countdown; cuando dispare, el job relee el estado: si el
        # estudiante ya fue marcado como tardanza/presente, no envía nada.
        if class_period.period_order == 1:
            countdown = settings.attendance_grace_minutes * 60
            for record in created:
                if record.status == AttendanceStatus.ABSENT:
                    notify_absence_first_hour.apply_async((str(record.id),), countdown=countdown)

        return [AttendanceRecordResponse.model_validate(r) for r in created]

    async def get_schedule(self, user_id: UUID, institution_id: UUID) -> list[ScheduleItem]:
        rows = await self.repo.get_teacher_schedule(
            user_id=user_id,
            institution_id=institution_id,
            academic_year=date.today().year,
        )
        return [
            ScheduleItem(
                class_period_id=r.class_period.id,
                day_of_week=r.class_period.day_of_week,
                period_order=r.class_period.period_order,
                name=r.class_period.name,
                start_time=r.class_period.start_time,
                end_time=r.class_period.end_time,
                group_name=r.group_name,
                grade_name=r.grade_name,
            )
            for r in rows
        ]

    async def list_justifications(self, user_id: UUID, institution_id: UUID) -> list[JustificationMessage]:
        rows = await self.repo.list_justifications_for_teacher(
            user_id=user_id,
            institution_id=institution_id,
        )
        return [
            JustificationMessage(
                record_id=r.record_id,
                student_name=r.student_name,
                photo_url=resolve_photo_url(self.storage, r.photo_url),
                group_name=r.group_name,
                grade_name=r.grade_name,
                date=r.date,
                reason=r.reason,
                submitted_at=r.submitted_at,
            )
            for r in rows
        ]

    async def mark_arrived(self, record_id: UUID, institution_id: UUID) -> AttendanceRecordResponse:
        record = await self.repo.get_record(record_id, institution_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
        if record.status == AttendanceStatus.LATE:
            return AttendanceRecordResponse.model_validate(record)
        if record.status != AttendanceStatus.ABSENT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede marcar la llegada de un estudiante ausente",
            )
        await self.repo.update_status(record, AttendanceStatus.LATE)
        return AttendanceRecordResponse.model_validate(record)

    # --- Justificación pública ---

    async def get_justification_info(self, token: UUID) -> JustificationInfo:
        tok = await self.repo.get_token_by_value(token)
        if not tok:
            return JustificationInfo(valid=False, message="El enlace no es válido.")
        if tok.used_at is not None:
            ctx = await self.repo.get_context(tok.attendance_record_id)
            return JustificationInfo(
                valid=False,
                already_justified=True,
                student_name=ctx and f"{ctx.student.first_name} {ctx.student.last_name}",
                date=ctx and ctx.record.date,
                group_name=ctx and ctx.group_name,
                grade_name=ctx and ctx.grade_name,
                message="Esta inasistencia ya fue justificada.",
            )
        if datetime.now() > tok.expires_at:
            return JustificationInfo(valid=False, message="El enlace ha expirado.")

        ctx = await self.repo.get_context(tok.attendance_record_id)
        if not ctx:
            return JustificationInfo(valid=False, message="El enlace no es válido.")
        return JustificationInfo(
            valid=True,
            student_name=f"{ctx.student.first_name} {ctx.student.last_name}",
            date=ctx.record.date,
            group_name=ctx.group_name,
            grade_name=ctx.grade_name,
        )

    async def submit_justification(self, token: UUID, reason: str) -> JustificationInfo:
        tok = await self.repo.get_token_by_value(token)
        if not tok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El enlace no es válido")
        if tok.used_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta inasistencia ya fue justificada")
        if datetime.now() > tok.expires_at:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="El enlace ha expirado")

        record = await self.repo.get_record_by_id(tok.attendance_record_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El registro no existe")

        await self.repo.create_justification(
            justification_id=uuid4(),
            record_id=record.id,
            token_id=tok.id,
            reason=reason.strip(),
        )
        await self.repo.mark_token_used(tok, datetime.now())
        await self.repo.update_status(record, AttendanceStatus.JUSTIFIED)

        ctx = await self.repo.get_context(record.id)
        return JustificationInfo(
            valid=True,
            already_justified=True,
            student_name=ctx and f"{ctx.student.first_name} {ctx.student.last_name}",
            date=ctx and ctx.record.date,
            group_name=ctx and ctx.group_name,
            grade_name=ctx and ctx.grade_name,
            message="Justificación registrada. Gracias.",
        )
