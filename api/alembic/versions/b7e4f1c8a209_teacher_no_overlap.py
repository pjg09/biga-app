"""un docente no puede estar en dos salones a la vez

`class_periods_no_time_overlap` (migración `f2d5a81c9e37`) protege el **aula**:
dos clases del mismo salón no pueden pisarse en el reloj. Pero no dice nada de la
**persona**, y eran dos invariantes distintos: nada impedía asignar al mismo
docente a las 07:00 del lunes en cuatro salones a la vez.

No es teórico. El seed de estadísticas repartía docentes por índice, sin mirar
ocupación, y dejó 120 pares de bloques solapados del mismo docente. El síntoma lo
vio el usuario en «Mis clases de hoy»: Carlos Docente con cuatro primeras horas
simultáneas (Décimo A, Décimo B, Once A, Once B), las cuatro con lista pendiente.
Asistencia filtra las clases del docente por `class_periods.user_id`, así que se
las mostraba todas — y en primera hora eso son cuatro tandas de notificación a
acudientes de salones donde ese docente no estuvo.

Igual que la anterior: un `EXCLUDE` no admite `NOT VALID`, así que los conflictos
previos se detectan y se reportan antes de intentar crearlo. No se reparan solos:
decidir cuál de las cuatro clases conserva al docente es del colegio, no de una
migración.

Revision ID: b7e4f1c8a209
Revises: f2d5a81c9e37
Create Date: 2026-08-17 07:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b7e4f1c8a209'
down_revision: Union[str, None] = 'f2d5a81c9e37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            conflictos text;
            total int;
        BEGIN
            SELECT count(*), string_agg(detalle, E'\\n')
            INTO total, conflictos
            FROM (
                SELECT format('%s %s: «%s» (%s-%s) choca con «%s» (%s-%s), día %s',
                              u.first_name, u.last_name,
                              a.name, a.start_time, a.end_time,
                              b.name, b.start_time, b.end_time, a.day_of_week) AS detalle
                FROM class_periods a
                JOIN class_periods b
                  ON a.user_id = b.user_id
                 AND a.day_of_week = b.day_of_week
                 AND a.id < b.id
                 AND a.start_time < b.end_time
                 AND b.start_time < a.end_time
                JOIN users u ON u.id = a.user_id
                LIMIT 20
            ) x;

            IF total > 0 THEN
                RAISE EXCEPTION
                    'Hay % docentes con bloques solapados; reasígnalos antes de migrar:%s%s',
                    total, E'\\n', conflictos;
            END IF;
        END $$
    """)

    op.execute("""
        ALTER TABLE class_periods
        ADD CONSTRAINT class_periods_teacher_no_overlap
        EXCLUDE USING gist (
            user_id WITH =,
            day_of_week WITH =,
            timerange(start_time, end_time) WITH &&
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE class_periods DROP CONSTRAINT class_periods_teacher_no_overlap")
