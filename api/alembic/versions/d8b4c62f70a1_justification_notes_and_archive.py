"""Excusas: cierre de caso (archived_at) y notas de seguimiento

Revision ID: d8b4c62f70a1
Revises: c7e1b93af204
Create Date: 2026-08-14

Espeja lo que ya existe para convivencia (`discipline_records.archived_at` +
`discipline_record_notes`), aplicado a las excusas de los acudientes.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d8b4c62f70a1"
down_revision = "c7e1b93af204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attendance_justifications",
        sa.Column("archived_at", sa.TIMESTAMP(), nullable=True),
    )

    op.create_table(
        "attendance_justification_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "justification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_justifications.id"),
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
        "idx_justification_notes_justification",
        "attendance_justification_notes",
        ["justification_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_justification_notes_justification", table_name="attendance_justification_notes"
    )
    op.drop_table("attendance_justification_notes")
    op.drop_column("attendance_justifications", "archived_at")
