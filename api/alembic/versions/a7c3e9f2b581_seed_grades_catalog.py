"""catálogo fijo de los 11 grados por institución

Los grados dejan de crearse desde la consola del admin y pasan a ser un
catálogo: los colegios públicos de Medellín tienen siempre los mismos 11
niveles (1º a 11º), así que dejarlo como alta manual solo abría la puerta a
erratas y a grados duplicados por nombre, sin ningún caso de uso real detrás.

Siembra los 11 niveles en **cada institución existente**, saltándose los que ya
tenga. Deliberadamente NO renombra ni borra grados ya creados: si un colegio
tenía su nivel 11 con otro nombre, se respeta — sus salones y matrículas
cuelgan de ese `grade_id`.

`grades` lleva `institution_id`, así que no puede ser una tabla global: cada
institución necesita sus propias 11 filas. Las nuevas instituciones las reciben
desde `scripts/seed_base.py`.

Revision ID: a7c3e9f2b581
Revises: f4a2b8d1c9e6
Create Date: 2026-08-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a7c3e9f2b581'
down_revision: Union[str, None] = 'f4a2b8d1c9e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nomenclatura estándar de la educación básica y media en Colombia.
GRADES = [
    (1, "Primero"), (2, "Segundo"), (3, "Tercero"), (4, "Cuarto"),
    (5, "Quinto"), (6, "Sexto"), (7, "Séptimo"), (8, "Octavo"),
    (9, "Noveno"), (10, "Décimo"), (11, "Once"),
]


def upgrade() -> None:
    # `WHERE NOT EXISTS` por (institución, nivel) y no `ON CONFLICT DO NOTHING`:
    # la constraint es UNIQUE(institution_id, level), así que un colegio con el
    # nivel 11 ya creado bajo otro nombre debe conservarlo, no chocar.
    for level, name in GRADES:
        op.execute(
            f"""
            INSERT INTO grades (id, institution_id, name, level, created_at)
            SELECT gen_random_uuid(), i.id, '{name}', {level}, NOW()
            FROM institutions i
            WHERE NOT EXISTS (
                SELECT 1 FROM grades g
                WHERE g.institution_id = i.id AND g.level = {level}
            )
            """
        )


def downgrade() -> None:
    # Solo borra los que esta migración pudo haber creado: los que conservan el
    # nombre del catálogo y no tienen ningún salón colgando. Un grado con
    # salones se queda — borrarlo rompería `groups.grade_id`.
    for level, name in GRADES:
        op.execute(
            f"""
            DELETE FROM grades g
            WHERE g.level = {level} AND g.name = '{name}'
              AND NOT EXISTS (SELECT 1 FROM groups gr WHERE gr.grade_id = g.id)
            """
        )
