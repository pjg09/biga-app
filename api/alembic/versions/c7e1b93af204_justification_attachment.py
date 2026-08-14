"""attendance_justifications: soporte adjunto (PDF o imagen)

Revision ID: c7e1b93af204
Revises: b2f47a1c9d63
Create Date: 2026-08-14

Las cuatro columnas son NULLABLE: el adjunto es opcional y las justificaciones
que ya existen se quedan sin él sin necesidad de backfill.
"""

from alembic import op
import sqlalchemy as sa

revision = "c7e1b93af204"
down_revision = "b2f47a1c9d63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attendance_justifications",
        sa.Column("attachment_key", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "attendance_justifications",
        sa.Column("attachment_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "attendance_justifications",
        sa.Column("attachment_content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "attendance_justifications",
        sa.Column("attachment_size_bytes", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendance_justifications", "attachment_size_bytes")
    op.drop_column("attendance_justifications", "attachment_content_type")
    op.drop_column("attendance_justifications", "attachment_filename")
    op.drop_column("attendance_justifications", "attachment_key")
