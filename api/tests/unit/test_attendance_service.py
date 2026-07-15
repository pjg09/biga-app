from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import AttendanceStatus
from app.schemas.attendance import AttendanceEntry, AttendanceSubmit
from app.services.attendance_service import AttendanceService


def _student(sid):
    return SimpleNamespace(
        id=sid, document_number="123", first_name="Ana", last_name="Pérez", photo_url=None
    )


def _service(repo):
    return AttendanceService(repo, MagicMock())


async def test_submit_rejects_non_submittable_status():
    repo = AsyncMock()
    service = _service(repo)
    sid = uuid4()
    data = AttendanceSubmit(class_period_id=uuid4(), entries=[AttendanceEntry(student_id=sid, status=AttendanceStatus.LATE)])
    with pytest.raises(HTTPException) as exc:
        await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert exc.value.status_code == 400


async def test_submit_rejects_unowned_class():
    repo = AsyncMock()
    repo.teacher_owns_class_period.return_value = None
    service = _service(repo)
    sid = uuid4()
    data = AttendanceSubmit(class_period_id=uuid4(), entries=[AttendanceEntry(student_id=sid, status=AttendanceStatus.PRESENT)])
    with pytest.raises(HTTPException) as exc:
        await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert exc.value.status_code == 404


async def test_submit_rejects_already_taken():
    repo = AsyncMock()
    repo.teacher_owns_class_period.return_value = SimpleNamespace(id=uuid4(), period_order=1, group_id=uuid4())
    repo.get_records_for_class.return_value = [SimpleNamespace(student_id=uuid4())]
    service = _service(repo)
    data = AttendanceSubmit(class_period_id=uuid4(), entries=[AttendanceEntry(student_id=uuid4(), status=AttendanceStatus.PRESENT)])
    with pytest.raises(HTTPException) as exc:
        await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert exc.value.status_code == 409


async def test_submit_rejects_roster_mismatch():
    repo = AsyncMock()
    cp = SimpleNamespace(id=uuid4(), period_order=1, group_id=uuid4())
    repo.teacher_owns_class_period.return_value = cp
    repo.get_records_for_class.return_value = []
    repo.get_group_roster.return_value = [_student(uuid4()), _student(uuid4())]
    service = _service(repo)
    data = AttendanceSubmit(class_period_id=uuid4(), entries=[AttendanceEntry(student_id=uuid4(), status=AttendanceStatus.PRESENT)])
    with pytest.raises(HTTPException) as exc:
        await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert exc.value.status_code == 400


async def test_submit_success_schedules_only_absent():
    s1, s2 = uuid4(), uuid4()
    cp = SimpleNamespace(id=uuid4(), period_order=1, group_id=uuid4())
    repo = AsyncMock()
    repo.teacher_owns_class_period.return_value = cp
    repo.get_records_for_class.return_value = []
    repo.get_group_roster.return_value = [_student(s1), _student(s2)]
    service = _service(repo)
    data = AttendanceSubmit(
        class_period_id=cp.id,
        entries=[
            AttendanceEntry(student_id=s1, status=AttendanceStatus.PRESENT),
            AttendanceEntry(student_id=s2, status=AttendanceStatus.ABSENT),
        ],
    )
    with patch("app.services.attendance_service.notify_absence_first_hour") as task:
        result = await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert len(result) == 2
    # Solo el ausente se programa para notificación.
    assert task.apply_async.call_count == 1


async def test_submit_non_first_hour_does_not_notify():
    # Clase que no es primera hora (period_order != 1): se registra la asistencia
    # pero NO se encola ninguna notificación al acudiente (scope 3.2).
    s1, s2 = uuid4(), uuid4()
    cp = SimpleNamespace(id=uuid4(), period_order=3, group_id=uuid4())
    repo = AsyncMock()
    repo.teacher_owns_class_period.return_value = cp
    repo.get_records_for_class.return_value = []
    repo.get_group_roster.return_value = [_student(s1), _student(s2)]
    service = _service(repo)
    data = AttendanceSubmit(
        class_period_id=cp.id,
        entries=[
            AttendanceEntry(student_id=s1, status=AttendanceStatus.PRESENT),
            AttendanceEntry(student_id=s2, status=AttendanceStatus.ABSENT),
        ],
    )
    with patch("app.services.attendance_service.notify_absence_first_hour") as task:
        result = await service.submit_attendance(user_id=uuid4(), institution_id=uuid4(), data=data)
    assert len(result) == 2
    assert task.apply_async.call_count == 0


async def test_mark_arrived_absent_becomes_late():
    record = SimpleNamespace(id=uuid4(), student_id=uuid4(), class_period_id=uuid4(),
                             date=date.today(), status=AttendanceStatus.ABSENT, created_at=datetime.now())
    repo = AsyncMock()
    repo.get_record.return_value = record

    async def _update(rec, st):
        rec.status = st
        return rec
    repo.update_status.side_effect = _update
    service = _service(repo)
    res = await service.mark_arrived(record_id=record.id, institution_id=uuid4())
    assert res.status == AttendanceStatus.LATE


async def test_mark_arrived_present_conflicts():
    record = SimpleNamespace(id=uuid4(), status=AttendanceStatus.PRESENT)
    repo = AsyncMock()
    repo.get_record.return_value = record
    service = _service(repo)
    with pytest.raises(HTTPException) as exc:
        await service.mark_arrived(record_id=record.id, institution_id=uuid4())
    assert exc.value.status_code == 409


async def test_justification_info_invalid_token():
    repo = AsyncMock()
    repo.get_token_by_value.return_value = None
    service = _service(repo)
    info = await service.get_justification_info(uuid4())
    assert info.valid is False


async def test_justification_info_expired():
    tok = SimpleNamespace(attendance_record_id=uuid4(), used_at=None,
                          expires_at=datetime.now() - timedelta(hours=1))
    repo = AsyncMock()
    repo.get_token_by_value.return_value = tok
    service = _service(repo)
    info = await service.get_justification_info(uuid4())
    assert info.valid is False


async def test_submit_justification_used_token_conflicts():
    tok = SimpleNamespace(id=uuid4(), attendance_record_id=uuid4(), used_at=datetime.now(),
                          expires_at=datetime.now() + timedelta(hours=1))
    repo = AsyncMock()
    repo.get_token_by_value.return_value = tok
    service = _service(repo)
    with pytest.raises(HTTPException) as exc:
        await service.submit_justification(token=uuid4(), reason="cita médica")
    assert exc.value.status_code == 409
