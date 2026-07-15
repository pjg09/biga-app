"""enable unaccent extension for accent-insensitive search

Habilita la extensión `unaccent` de PostgreSQL para que la búsqueda de
estudiantes por nombre sea insensible a acentos (ej. "Lopez" encuentra "López").
El repositorio envuelve columna y patrón en `unaccent(...)` en el WHERE.

Revision ID: d4a2c7e91b05
Revises: c3e8f1a6b9d2
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4a2c7e91b05'
down_revision: Union[str, None] = 'c3e8f1a6b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent")
