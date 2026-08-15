"""materia del docente en user_groups

Agrega `subject` a `user_groups`: la materia que ese docente dicta en ese
salón. Nullable porque las asignaciones existentes no tienen valor.

Revision ID: c4d8f2a6b1e9
Revises: a1b2c3d4e5f6
Create Date: 2026-08-14 18:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d8f2a6b1e9'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_groups",
        sa.Column("subject", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_groups", "subject")
