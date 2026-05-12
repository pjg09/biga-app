from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", "academic_year"),)

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    academic_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
