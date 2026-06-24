from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import NotificationLog


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_log(
        self,
        institution_id: UUID,
        type: NotificationType,
        student_id: UUID,
        guardian_id: UUID,
        email_to: str,
        subject: str,
        status: NotificationStatus,
        error_message: str | None = None,
        sent_at: datetime | None = None,
    ) -> NotificationLog:
        log = NotificationLog(
            id=uuid4(),
            institution_id=institution_id,
            type=type,
            student_id=student_id,
            guardian_id=guardian_id,
            email_to=email_to,
            subject=subject,
            status=status,
            error_message=error_message,
            sent_at=sent_at,
        )
        self.session.add(log)
        await self.session.flush()
        return log
