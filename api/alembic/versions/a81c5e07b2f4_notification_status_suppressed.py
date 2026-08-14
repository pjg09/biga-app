"""notification_status: valor SUPPRESSED

Revision ID: a81c5e07b2f4
Revises: f6d9a4c30e18
Create Date: 2026-08-10

Distingue "no se intentó enviar a propósito" (lead duplicado dentro de la ventana
de 24h) de PENDING, que significa "encolado y sin resolver todavía". Sin este
valor, una fila atascada en PENDING por un worker caído es indistinguible de una
supresión deliberada.
"""

from alembic import op

revision = "a81c5e07b2f4"
down_revision = "f6d9a4c30e18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE no corre dentro del bloque transaccional de
    # Alembic; hay que sacarlo con autocommit_block (ver migración c3e8f1a6b9d2).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_status ADD VALUE IF NOT EXISTS 'SUPPRESSED'")


def downgrade() -> None:
    # Postgres no permite quitar un valor de un ENUM sin recrear el tipo y
    # reescribir todas las columnas que lo usan. No se revierte.
    pass
