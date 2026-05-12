from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClassPeriod(Base):
    __tablename__ = "class_periods"
    __table_args__ = (
        UniqueConstraint("group_id", "period_order", "day_of_week"),
        CheckConstraint("day_of_week BETWEEN 1 AND 5", name="check_day_of_week"),
        CheckConstraint("period_order >= 1", name="check_period_order"),
        CheckConstraint("start_time < end_time", name="check_time_order"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
