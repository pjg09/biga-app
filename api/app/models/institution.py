from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import String, Time, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nit: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    pae_delivery_end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
