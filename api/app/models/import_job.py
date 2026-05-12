from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ImportJobStatus, ImportJobType


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False)
    type: Mapped[ImportJobType] = mapped_column(
        SAEnum(ImportJobType, native_enum=True, name="import_job_type"), nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        SAEnum(ImportJobStatus, native_enum=True, name="import_job_status"),
        nullable=False,
        server_default="PENDING",
    )
    total_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
