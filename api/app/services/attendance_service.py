import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.config import settings
from app.core.photos import resolve_photo_url
from app.jobs.attendance_jobs import notify_absence_first_hour
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.guardian_repository import GuardianRepository
from app.schemas.attendance import (
    AbsenceDetail,
    AbsenceItem,
    AbsenceNoteResponse,
    AttendanceRecordResponse,
    AttendanceStudentItem,
    AttendanceSubmit,
    ClassAttendanceResponse,
    ClassSlot,
    JustificationDetail,
    JustificationInfo,
    JustificationMessage,
    JustificationNoteResponse,
    ScheduleItem,
    TodayClassesResponse,
)

_SUBMITTABLE = {AttendanceStatus.PRESENT, AttendanceStatus.ABSENT}

# Tipos que el acudiente puede adjuntar como soporte, y la extensión con la que
# se guarda el objeto. La extensión sale de aquí, nunca del nombre del archivo.
_ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@dataclass
class _StoredAttachment:
    key: str
    filename: str
    content_type: str
    size_bytes: int


def _safe_filename(raw: str | None) -> str:
    """Nombre presentable: sin rutas, sin caracteres raros y acotado.

    El nombre lo elige quien sube el archivo, así que se trata como entrada
    hostil: se descarta cualquier componente de ruta (`../`, `C:\\...`) antes de
    que llegue al front, donde acabará en un atributo `download`.
    """
    if not raw:
        return ""
    # Basename tanto de rutas POSIX como de Windows: los navegadores de escritorio
    # mandan a veces la ruta completa.
    name = PureWindowsPath(PurePosixPath(raw).name).name
    name = unicodedata.normalize("NFC", name).replace("\x00", "").strip()
    name = "".join(c for c in name if c.isprintable() and c not in '/\\<>:"|?*')
    return name[:120]


class AttendanceService:
    def __init__(
        self,
        repo: AttendanceRepository,
        storage: S3StorageAdapter,
        guardian_repo: GuardianRepository | None = None,
    ):
        self.storage = storage
        self.repo = repo
        # Opcional para no romper a quien ya construía el service con dos
        # argumentos; solo lo necesita el detalle de una inasistencia, que
        # muestra a quién habría que llamar.
        self.guardian_repo = guardian_repo

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

        now = datetime.now()
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

    async def list_justifications(
        self,
        user_id: UUID,
        institution_id: UUID,
        student_id: UUID | None = None,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[JustificationMessage]:
        rows = await self.repo.list_justifications_for_teacher(
            user_id=user_id,
            institution_id=institution_id,
            student_id=student_id,
            include_archived=include_archived,
            skip=skip,
            limit=limit,
        )
        return [
            JustificationMessage(
                id=r.justification_id,
                record_id=r.record_id,
                student_id=r.student_id,
                student_name=r.student_name,
                photo_url=resolve_photo_url(self.storage, r.photo_url),
                group_name=r.group_name,
                grade_name=r.grade_name,
                date=r.date,
                reason=r.reason,
                submitted_at=r.submitted_at,
                attachment_url=self.storage.get_url(r.attachment_key) if r.attachment_key else None,
                attachment_filename=r.attachment_filename,
                attachment_content_type=r.attachment_content_type,
                note_count=r.note_count,
                archived=r.archived,
            )
            for r in rows
        ]

    async def get_justification_detail(
        self, justification_id: UUID, institution_id: UUID
    ) -> JustificationDetail:
        row = await self.repo.get_justification_detail(justification_id, institution_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excusa no encontrada")

        j = row.justification
        notes = await self.repo.list_justification_notes(justification_id)
        return JustificationDetail(
            id=j.id,
            record_id=row.record_id,
            student_id=row.student_id,
            student_name=row.student_name,
            photo_url=resolve_photo_url(self.storage, row.photo_url),
            grade_name=row.grade_name,
            group_name=row.group_name,
            date=row.date,
            reason=j.reason,
            submitted_at=j.submitted_at,
            attachment_url=self.storage.get_url(j.attachment_key) if j.attachment_key else None,
            attachment_filename=j.attachment_filename,
            attachment_content_type=j.attachment_content_type,
            attachment_size_bytes=j.attachment_size_bytes,
            notes=[
                JustificationNoteResponse(
                    id=n.id, note=n.note, author_name=n.author_name, created_at=n.created_at
                )
                for n in notes
            ],
            archived=j.archived_at is not None,
        )

    async def add_justification_note(
        self, justification_id: UUID, user_id: UUID, institution_id: UUID, note: str
    ) -> JustificationNoteResponse:
        justification = await self.repo.get_justification(justification_id, institution_id)
        if not justification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excusa no encontrada")

        texto = note.strip()
        if not texto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="La nota no puede estar vacía"
            )

        saved = await self.repo.add_justification_note(
            note_id=uuid4(),
            justification_id=justification_id,
            institution_id=institution_id,
            author_user_id=user_id,
            note=texto,
        )
        # El nombre del autor se resuelve releyendo las notas: es quien acaba de
        # escribirla, pero pedirlo al repo evita duplicar aquí el join a users.
        notes = await self.repo.list_justification_notes(justification_id)
        creada = next(n for n in notes if n.id == saved.id)
        return JustificationNoteResponse(
            id=creada.id, note=creada.note, author_name=creada.author_name, created_at=creada.created_at
        )

    async def set_justification_archived(
        self, justification_id: UUID, institution_id: UUID, archived: bool
    ) -> None:
        """Cierra o reabre el caso. No borra: la excusa sigue consultable."""
        justification = await self.repo.get_justification(justification_id, institution_id)
        if not justification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excusa no encontrada")
        await self.repo.set_justification_archived(
            justification, datetime.now() if archived else None
        )

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

    # --- Soporte adjunto a la justificación ---

    async def _store_attachment(self, upload: UploadFile, record) -> _StoredAttachment:
        """Valida y sube el soporte del acudiente. Devuelve sus metadatos.

        El endpoint que llega aquí es **público**: la única credencial es el
        token del enlace. Por eso se valida tipo y tamaño en el servidor y no se
        confía en el `content-type` que declara el cliente para nombrar el
        objeto — la extensión sale de la tabla blanca, no del nombre original.
        """
        content_type = (upload.content_type or "").split(";")[0].strip().lower()
        ext = _ALLOWED_ATTACHMENT_TYPES.get(content_type)
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato no admitido. Adjunte un PDF o una imagen (JPG, PNG o WEBP).",
            )

        max_bytes = settings.justification_max_upload_mb * 1024 * 1024
        # `upload.size` lo calcula Starlette al parsear el multipart; se mira
        # antes de leer para no traer a memoria un archivo enorme.
        if upload.size is not None and upload.size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo supera el máximo de {settings.justification_max_upload_mb} MB.",
            )

        data = await upload.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío."
            )
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo supera el máximo de {settings.justification_max_upload_mb} MB.",
            )

        # Una justificación por registro (UNIQUE), así que el record_id basta
        # como key y no hay colisiones posibles.
        key = f"justifications/{record.institution_id}/{record.id}.{ext}"
        self.storage.upload(key, data, content_type)

        return _StoredAttachment(
            key=key,
            # El nombre original solo se usa para mostrar y descargar; se recorta
            # y se limpia de rutas para que no viaje un "../.." al front.
            filename=_safe_filename(upload.filename) or f"soporte.{ext}",
            content_type=content_type,
            size_bytes=len(data),
        )

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

    async def submit_justification(
        self,
        token: UUID,
        reason: str,
        attachment: UploadFile | None = None,
    ) -> JustificationInfo:
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

        att = await self._store_attachment(attachment, record) if attachment else None

        await self.repo.create_justification(
            justification_id=uuid4(),
            record_id=record.id,
            token_id=tok.id,
            reason=reason.strip(),
            attachment_key=att.key if att else None,
            attachment_filename=att.filename if att else None,
            attachment_content_type=att.content_type if att else None,
            attachment_size_bytes=att.size_bytes if att else None,
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

    # --- Inasistencias de primera hora sin justificar ---

    async def list_unjustified_absences(
        self,
        user_id: UUID,
        institution_id: UUID,
        student_id: UUID | None = None,
        include_closed: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AbsenceItem]:
        rows = await self.repo.list_unjustified_absences(
            user_id=user_id, institution_id=institution_id,
            student_id=student_id, include_closed=include_closed,
            skip=skip, limit=limit,
        )
        return [
            AbsenceItem(
                record_id=r.record_id,
                student_id=r.student_id,
                student_name=r.student_name,
                photo_url=resolve_photo_url(self.storage, r.photo_url),
                grade_name=r.grade_name,
                group_name=r.group_name,
                date=r.date,
                period_name=r.period_name,
                start_time=r.start_time,
                note_count=r.note_count,
                guardian_notified=r.guardian_notified,
                closed=r.closed,
            )
            for r in rows
        ]

    async def get_absence_detail(
        self, record_id: UUID, user_id: UUID, institution_id: UUID
    ) -> AbsenceDetail:
        row = await self.repo.get_unjustified_absence(record_id, user_id, institution_id)
        if not row:
            # También cae aquí una inasistencia que acaba de ser justificada: ya
            # no pertenece a esta sección, vive en Mensajes.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La inasistencia no existe, no es tuya o ya fue justificada",
            )

        guardian = (
            await self.guardian_repo.get_primary(row.student_id)
            if self.guardian_repo else None
        )
        notes = await self.repo.list_absence_notes(record_id)
        return AbsenceDetail(
            record_id=row.record_id,
            student_id=row.student_id,
            student_name=row.student_name,
            photo_url=resolve_photo_url(self.storage, row.photo_url),
            grade_name=row.grade_name,
            group_name=row.group_name,
            date=row.date,
            period_name=row.period_name,
            start_time=row.start_time,
            end_time=row.end_time,
            recorded_at=row.recorded_at,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            guardian_notified=row.guardian_notified,
            guardian_email=guardian.email if guardian else None,
            closed=row.closed,
            notes=[
                AbsenceNoteResponse(
                    id=n.id, note=n.note, author_name=n.author_name, created_at=n.created_at
                )
                for n in notes
            ],
        )

    async def add_absence_note(
        self, record_id: UUID, user_id: UUID, institution_id: UUID, note: str
    ) -> AbsenceNoteResponse:
        row = await self.repo.get_unjustified_absence(record_id, user_id, institution_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La inasistencia no existe, no es tuya o ya fue justificada",
            )
        texto = note.strip()
        if not texto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="La nota no puede estar vacía"
            )

        saved = await self.repo.add_absence_note(
            note_id=uuid4(), record_id=record_id, institution_id=institution_id,
            author_user_id=user_id, note=texto,
        )
        notes = await self.repo.list_absence_notes(record_id)
        creada = next(n for n in notes if n.id == saved.id)
        return AbsenceNoteResponse(
            id=creada.id, note=creada.note,
            author_name=creada.author_name, created_at=creada.created_at,
        )

    async def set_absence_closed(
        self, record_id: UUID, user_id: UUID, institution_id: UUID, closed: bool
    ) -> None:
        """Cierra o reabre el seguimiento de una inasistencia sin justificar.

        Para casos en los que el enlace venció o simplemente no hubo nada más
        que hacer. No toca el registro de asistencia como tal: sigue contando
        como inasistencia en el roster y en las estadísticas.
        """
        row = await self.repo.get_unjustified_absence(record_id, user_id, institution_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La inasistencia no existe, no es tuya o ya fue justificada",
            )
        await self.repo.set_absence_closed(record_id, datetime.now() if closed else None)
