"""pae integrity hashes

Agrega las dos capas de la cadena de integridad PAE:
  - pae_enrollments.enrollment_hash (capa 1)
  - pae_deliveries.delivery_hash    (capa 2, encadenada sobre la capa 1)

La columna delivery_hash existía en el modelo desde el inicio pero nunca llegó
a la migración inicial, por lo que cualquier INSERT en pae_deliveries fallaba.
Esta revisión la incorpora junto con enrollment_hash.

Ambas columnas se crean NOT NULL sin default: los hashes los computa la
aplicación con una clave que nunca vive en la BD. Las tablas están vacías en
este punto (no existía ruta para poblarlas), por lo que la adición es segura.

Revision ID: b7c1a9e4d2f0
Revises: edf3b7ed3385
Create Date: 2026-06-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c1a9e4d2f0'
down_revision: Union[str, None] = 'edf3b7ed3385'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pae_enrollments', sa.Column('enrollment_hash', sa.String(length=64), nullable=False))
    op.alter_column('pae_enrollments', 'enrolled_at', server_default=None)
    op.add_column('pae_deliveries', sa.Column('delivery_hash', sa.String(length=64), nullable=False))


def downgrade() -> None:
    op.drop_column('pae_deliveries', 'delivery_hash')
    op.alter_column('pae_enrollments', 'enrolled_at', server_default=sa.text('now()'))
    op.drop_column('pae_enrollments', 'enrollment_hash')
