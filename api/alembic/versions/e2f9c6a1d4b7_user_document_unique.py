"""documento único por institución en users

Agrega UNIQUE(institution_id, document_number) a `users` — mismo patrón que
`students.document_number`. Antes no había ningún chequeo de unicidad sobre
este campo (solo `email` lo tenía).

Revision ID: e2f9c6a1d4b7
Revises: d7e1a4c8f5b3
Create Date: 2026-08-14 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'e2f9c6a1d4b7'
down_revision: Union[str, None] = 'd7e1a4c8f5b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_users_institution_id_document_number",
        "users",
        ["institution_id", "document_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_users_institution_id_document_number",
        "users",
        type_="unique",
    )
