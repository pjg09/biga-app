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
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="check_day_of_week"),
        CheckConstraint("period_order >= 1", name="check_period_order"),
        CheckConstraint("span >= 1", name="check_span_positive"),
        CheckConstraint("start_time < end_time", name="check_time_order"),
        Index("idx_class_periods_group_day", "group_id", "day_of_week"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Periodos consecutivos que ocupa el bloque. 1 = normal, 2 = clase doble
    # (ocupa `period_order` y `period_order + 1`). El no-solapamiento lo
    # garantiza el EXCLUDE de la migración `e9a3b7c2d418`, que SQLAlchemy no
    # modela: vive solo en la BD y está documentado en database-schema.md.
    span: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1", default=1)
    # Nullable a propósito: un horario a medio armar debe poder guardarse, y los
    # bloques anteriores a la migración `c5b9e2f47a13` no tienen con qué llenarlo.
    subject_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True
    )
    # NOT NULL (migración `d6c1f8a390b4`): Asistencia filtra las clases del
    # docente por esta columna, así que un bloque sin docente sería un bloque
    # donde nadie toma lista — y en primera hora, una notificación al acudiente
    # que nunca se envía.
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
