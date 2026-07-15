"""discipline record notes + archive flag

Agrega el historial de convivencia del docente:
- columna `archived_at` en `discipline_records` (ocultar del panel sin borrar).
- tabla `discipline_record_notes` (notas de seguimiento append-only).

Revision ID: e5b3f8c210a7
Revises: d4a2c7e91b05
Create Date: 2026-07-15 00:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'e5b3f8c210a7'
down_revision: Union[str, None] = 'd4a2c7e91b05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "discipline_records",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "discipline_record_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("discipline_record_id", UUID(as_uuid=True), sa.ForeignKey("discipline_records.id"), nullable=False),
        sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("author_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_record_notes_record",
        "discipline_record_notes",
        ["discipline_record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_record_notes_record", table_name="discipline_record_notes")
    op.drop_table("discipline_record_notes")
    op.drop_column("discipline_records", "archived_at")
