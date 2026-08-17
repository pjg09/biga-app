"""horario por hora real: EXCLUDE sobre el reloj y fuera `span`

El horario se dibujaba como una rejilla de filas = `period_order`, así que todas
las celdas medían lo mismo durase la clase 50 minutos o dos horas, y el descanso
de media mañana no existía visualmente. Con una vista tipo calendario (alto
proporcional a la duración) esa mentira deja de ser sostenible.

El cambio de fondo no es de CSS, es de invariante. Hasta aquí la BD impedía que
dos bloques del mismo salón y día se solaparan **en número de orden**:

    EXCLUDE ... int4range(period_order, period_order + span) WITH &&

Eso protege lo que no importa. Los bloques no chocan por número, chocan por
reloj. La BD de desarrollo tenía la prueba: un bloque `period_order = 2,
span = 2` de 07:00–08:50 conviviendo con el `period_order = 1` de 07:00–07:50 —
rangos de orden `[2,4)` y `[1,2)`, que no se tocan, y una hora entera pisada.

Por eso aquí:

1. Se crea el tipo `timerange` (PostgreSQL no trae range de `time`) y el
   `EXCLUDE` pasa a ser sobre `timerange(start_time, end_time)`.
2. Se elimina `span`. La duración la dan `start_time`/`end_time` y nada más;
   tener las dos cosas permitía guardar un `span = 2` de 50 minutos.
3. `period_order` se queda —Asistencia notifica al acudiente en `period_order =
   1`— pero pasa a ser **derivado**: la app lo renumera `1..N` por `start_time`
   dentro de cada (salón, día). Esta migración hace esa primera renumeración.

Un `EXCLUDE` no admite `NOT VALID` (solo `CHECK` y `FK`), así que no se puede
añadir "a validar luego": si ya hay solapes, el `ALTER TABLE` revienta con un
mensaje que no dice cuáles. Se detectan antes y se aborta nombrándolos. No se
reparan automáticamente: recortar el `end_time` de una de las dos clases es
decidir por el colegio cuál cede.

Revision ID: f2d5a81c9e37
Revises: e9a3b7c2d418
Create Date: 2026-08-15 23:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2d5a81c9e37'
down_revision: Union[str, None] = 'e9a3b7c2d418'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Abortar con detalle si el dato actual ya se solapa en el reloj.
    op.execute("""
        DO $$
        DECLARE
            conflictos text;
        BEGIN
            SELECT string_agg(
                format('salón %s, día %s: «%s» %s-%s choca con «%s» %s-%s',
                       a.group_id, a.day_of_week,
                       a.name, a.start_time, a.end_time,
                       b.name, b.start_time, b.end_time),
                E'\\n')
            INTO conflictos
            FROM class_periods a
            JOIN class_periods b
              ON a.group_id = b.group_id
             AND a.day_of_week = b.day_of_week
             AND a.id < b.id
             AND a.start_time < b.end_time
             AND b.start_time < a.end_time;

            IF conflictos IS NOT NULL THEN
                RAISE EXCEPTION
                    'Hay bloques que se solapan en el reloj; corrígelos antes de migrar:%s%s',
                    E'\\n', conflictos;
            END IF;
        END $$
    """)

    # 2. El invariante se muda del rango de órdenes al rango de horas.
    op.execute("ALTER TABLE class_periods DROP CONSTRAINT class_periods_no_overlap")
    op.drop_constraint("check_span_positive", "class_periods", type_="check")
    op.drop_column("class_periods", "span")

    # `subtype_diff` es opcional: solo afina la penalización del GiST, y acá son
    # decenas de filas por salón. `range_ops` de GiST vale para cualquier range
    # type, así que no hace falta declarar operator class en el EXCLUDE.
    op.execute("CREATE TYPE timerange AS RANGE (subtype = time)")
    op.execute("""
        ALTER TABLE class_periods
        ADD CONSTRAINT class_periods_no_time_overlap
        EXCLUDE USING gist (
            group_id WITH =,
            day_of_week WITH =,
            timerange(start_time, end_time) WITH &&
        )
    """)

    # 3. `period_order` pasa a ser derivado: denso 1..N por hora de inicio.
    #    Dos fases por la UNIQUE(group_id, period_order, day_of_week) — un solo
    #    UPDATE que permuta valores la viola fila a fila, no al final.
    op.execute("""
        UPDATE class_periods SET period_order = period_order + 1000
    """)
    op.execute("""
        UPDATE class_periods cp
        SET period_order = nuevo.orden
        FROM (
            SELECT id, row_number() OVER (
                       PARTITION BY group_id, day_of_week ORDER BY start_time
                   ) AS orden
            FROM class_periods
        ) AS nuevo
        WHERE cp.id = nuevo.id
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE class_periods DROP CONSTRAINT class_periods_no_time_overlap")
    op.execute("DROP TYPE timerange")
    # `span` vuelve como 1 en todas las filas: la información de qué bloque era
    # doble no se puede reconstruir desde las horas sin inventar la duración del
    # periodo base. Los `period_order` renumerados tampoco se revierten.
    op.add_column(
        "class_periods",
        sa.Column("span", sa.SmallInteger(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("check_span_positive", "class_periods", "span >= 1")
    op.execute("""
        ALTER TABLE class_periods
        ADD CONSTRAINT class_periods_no_overlap
        EXCLUDE USING gist (
            group_id WITH =,
            day_of_week WITH =,
            int4range(period_order, period_order + span) WITH &&
        )
    """)
