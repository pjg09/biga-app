from datetime import date, timedelta
from uuid import UUID

from app.repositories.admin_repository import AdminRepository
from app.schemas.admin import AdminStats


class AdminService:
    def __init__(self, repo: AdminRepository):
        self.repo = repo

    async def get_stats(self, institution_id: UUID) -> AdminStats:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)

        students = await self.repo.count_active_students(institution_id)
        users = await self.repo.count_users_by_role(institution_id)
        teachers = users.get("TEACHER", 0)
        pae_ops = users.get("PAE_OPERATOR", 0)
        admins = users.get("ADMIN", 0)

        pae_enrolled = await self.repo.count_pae_enrolled(institution_id, today.year)
        pae_today = await self.repo.count_pae_deliveries_between(institution_id, today, today)
        pae_week = await self.repo.count_pae_deliveries_between(institution_id, week_start, week_end)
        claim_rate = round(pae_today / pae_enrolled * 100, 1) if pae_enrolled else 0.0

        att = await self.repo.attendance_counts_today(institution_id, today)
        present = att.get("PRESENT", 0)
        absent = att.get("ABSENT", 0)
        late = att.get("LATE", 0)
        justified = att.get("JUSTIFIED", 0)
        att_total = present + absent + late + justified
        att_rate = round((present + late) / att_total * 100, 1) if att_total else 0.0

        departures = await self.repo.count_departures_today(institution_id, today)

        discipline_total = await self.repo.count_discipline_records(institution_id)
        sev = await self.repo.discipline_severity_counts(institution_id)

        notif = await self.repo.notification_counts(institution_id)

        return AdminStats(
            date=today,
            students_active=students,
            staff_total=teachers + pae_ops + admins,
            teachers=teachers,
            pae_operators=pae_ops,
            pae_enrolled=pae_enrolled,
            pae_delivered_today=pae_today,
            pae_delivered_week=pae_week,
            pae_claim_rate=claim_rate,
            attendance_present_today=present,
            attendance_absent_today=absent,
            attendance_late_today=late,
            attendance_justified_today=justified,
            attendance_rate_today=att_rate,
            departures_today=departures,
            discipline_records=discipline_total,
            discipline_leve=sev.get("LEVE", 0),
            discipline_moderada=sev.get("MODERADA", 0),
            discipline_grave=sev.get("GRAVE", 0),
            notifications_sent=notif.get("SENT", 0),
            notifications_failed=notif.get("FAILED", 0),
            notifications_pending=notif.get("PENDING", 0),
        )
