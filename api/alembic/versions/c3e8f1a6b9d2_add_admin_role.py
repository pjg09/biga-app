"""add ADMIN to user_role enum

Agrega el valor 'ADMIN' al tipo enum nativo `user_role`. PostgreSQL no permite
`ALTER TYPE ... ADD VALUE` dentro del bloque transaccional que Alembic abre por
defecto, así que se ejecuta en un autocommit_block.

Revision ID: c3e8f1a6b9d2
Revises: b7c1a9e4d2f0
Create Date: 2026-06-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3e8f1a6b9d2'
down_revision: Union[str, None] = 'b7c1a9e4d2f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade() -> None:
    # PostgreSQL no soporta quitar un valor de un enum sin recrear el tipo.
    # No-op intencional.
    pass
