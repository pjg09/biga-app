"""materia y docente por bloque horario

Hasta ahora el horario no podía decir "lunes 3ª hora, Matemáticas con Carlos":
la materia vivía duplicada en `class_periods.name` (texto libre que ya divergía
del catálogo — 4 de 6 nombres del seed no existían en `subjects`) y el docente
solo estaba a nivel de salón entero, en `user_groups`.

Ambas columnas son **nullable a propósito**: un horario a medio armar tiene que
poder guardarse, y los bloques ya existentes no tienen con qué rellenarlas.

Cambio **aditivo**: no toca `user_groups` ni el join que usa Asistencia para
"Mis clases de hoy", así que el comportamiento de ese módulo no cambia.

También alinea el CHECK de `day_of_week` con la realidad: la BD ya permitía
1..7 mientras el modelo declaraba 1..5, y existen bloques en sábado creados por
API. Se deja en 1..7 y se corrige el modelo, en vez de estrechar el CHECK y
tener que borrar esas filas.

Revision ID: c5b9e2f47a13
Revises: b8d4f1a7c360
Create Date: 2026-08-15 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5b9e2f47a13'
down_revision: Union[str, None] = 'b8d4f1a7c360'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("class_periods", sa.Column("subject_id", sa.UUID(), nullable=True))
    op.add_column("class_periods", sa.Column("user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "class_periods_subject_id_fkey", "class_periods", "subjects", ["subject_id"], ["id"]
    )
    op.create_foreign_key(
        "class_periods_user_id_fkey", "class_periods", "users", ["user_id"], ["id"]
    )
    # Índices para la rejilla: se filtra por salón y se pinta por día.
    op.create_index("idx_class_periods_group_day", "class_periods", ["group_id", "day_of_week"])


def downgrade() -> None:
    op.drop_index("idx_class_periods_group_day", table_name="class_periods")
    op.drop_constraint("class_periods_user_id_fkey", "class_periods", type_="foreignkey")
    op.drop_constraint("class_periods_subject_id_fkey", "class_periods", type_="foreignkey")
    op.drop_column("class_periods", "user_id")
    op.drop_column("class_periods", "subject_id")
