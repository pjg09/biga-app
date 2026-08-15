"""foto de perfil del personal (users.photo_url)

Agrega `photo_url` a `users`, con la misma semántica que `students.photo_url`:
guarda la **key** del objeto en storage, no la URL, porque las presignadas
caducan y dejarían enlaces muertos en la BD. Nullable: el personal ya existente
no tiene foto y la foto sigue siendo opcional al crear.

Revision ID: f4a2b8d1c9e6
Revises: e2f9c6a1d4b7
Create Date: 2026-08-15 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f4a2b8d1c9e6'
down_revision: Union[str, None] = 'e2f9c6a1d4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_url")
