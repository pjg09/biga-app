"""catálogo de materias

Convierte `user_groups.subject` (texto libre) en un catálogo real:
- tabla `subjects` (institution_id, name), UNIQUE(institution_id, name).
- `user_groups.subject_id` (FK, nullable) reemplaza a `user_groups.subject`.

Backfill: cada valor distinto de `subject` ya cargado se convierte en una fila
de `subjects` (agrupado por institución vía `groups.institution_id`, porque
`user_groups` no tiene institution_id propio) y `user_groups.subject_id` se
apunta a esa fila. Después se elimina la columna vieja.

Revision ID: d7e1a4c8f5b3
Revises: c4d8f2a6b1e9
Create Date: 2026-08-14 19:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'd7e1a4c8f5b3'
down_revision: Union[str, None] = 'c4d8f2a6b1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", UUID(as_uuid=True), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("institution_id", "name", name="uq_subjects_institution_id_name"),
    )

    op.add_column(
        "user_groups",
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id"), nullable=True),
    )

    # gen_random_uuid() es built-in desde Postgres 13, no requiere extensión.
    op.execute("""
        INSERT INTO subjects (id, institution_id, name, created_at)
        SELECT gen_random_uuid(), g.institution_id, ug.subject, now()
        FROM user_groups ug
        JOIN groups g ON g.id = ug.group_id
        WHERE ug.subject IS NOT NULL
        GROUP BY g.institution_id, ug.subject
    """)
    op.execute("""
        UPDATE user_groups ug
        SET subject_id = s.id
        FROM subjects s, groups g
        WHERE ug.group_id = g.id
          AND s.institution_id = g.institution_id
          AND s.name = ug.subject
    """)

    op.drop_column("user_groups", "subject")


def downgrade() -> None:
    op.add_column("user_groups", sa.Column("subject", sa.String(length=100), nullable=True))
    op.execute("""
        UPDATE user_groups ug
        SET subject = s.name
        FROM subjects s
        WHERE ug.subject_id = s.id
    """)
    op.drop_column("user_groups", "subject_id")
    op.drop_table("subjects")
