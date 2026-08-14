"""add PAE_LATE_CLAIM_CORRECTION to notification_type enum

Agrega el valor 'PAE_LATE_CLAIM_CORRECTION' al tipo enum nativo
`notification_type`. PostgreSQL no permite `ALTER TYPE ... ADD VALUE` dentro
del bloque transaccional que Alembic abre por defecto, así que se ejecuta en
un autocommit_block (ver c3e8f1a6b9d2 para el mismo patrón).

Revision ID: a1b2c3d4e5f6
Revises: f3c9e05a71d8
Create Date: 2026-08-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3c9e05a71d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'PAE_LATE_CLAIM_CORRECTION'")


def downgrade() -> None:
    # PostgreSQL no soporta quitar un valor de un enum sin recrear el tipo.
    # No-op intencional.
    pass
