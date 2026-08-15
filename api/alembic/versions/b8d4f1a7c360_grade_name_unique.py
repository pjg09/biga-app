"""nombre de grado único por institución

`grades` ya tenía `UNIQUE(institution_id, level)`, pero `name` quedaba libre: se
podían crear dos grados con el mismo nombre y distinto nivel. El desplegable de
Grado del alta de salones muestra solo `grades.name`, así que esos dos grados
serían indistinguibles al matricular.

Hoy los grados son un catálogo sembrado (`a7c3e9f2b581`) y no hay alta manual,
así que en la práctica no puede darse — esto cierra la puerta a nivel de BD por
si alguna vez se reabre. Mismo patrón por institución que `subjects.name` y
`users.document_number`.

Revision ID: b8d4f1a7c360
Revises: a7c3e9f2b581
Create Date: 2026-08-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b8d4f1a7c360'
down_revision: Union[str, None] = 'a7c3e9f2b581'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_grades_institution_id_name",
        "grades",
        ["institution_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_grades_institution_id_name", "grades", type_="unique")
