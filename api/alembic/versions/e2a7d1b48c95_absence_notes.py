"""attendance_absence_notes: seguimiento de inasistencias sin justificar

Revision ID: e2a7d1b48c95
Revises: d8b4c62f70a1
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e2a7d1b48c95"
down_revision = "d8b4c62f70a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_absence_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "attendance_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_records.id"),
            nullable=False,
        ),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_absence_notes_record",
        "attendance_absence_notes",
        ["attendance_record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_absence_notes_record", table_name="attendance_absence_notes")
    op.drop_table("attendance_absence_notes")
