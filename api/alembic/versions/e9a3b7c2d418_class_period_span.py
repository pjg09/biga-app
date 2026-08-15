"""clases de duración variable (class_periods.span)

No todas las clases duran lo mismo: hay materias de un bloque y materias de dos
bloques seguidos ("clase doble"). Antes esto no se podía expresar — cada
`class_period` ocupaba exactamente un `period_order`, así que una clase doble
había que partirla en dos filas y la rejilla mostraba dos celdas independientes.

`span` dice cuántos periodos consecutivos ocupa el bloque: 1 = normal,
2 = doble. Un bloque con `period_order = 2` y `span = 2` ocupa el 2 y el 3.

La `UNIQUE(group_id, period_order, day_of_week)` que ya existía **no basta** con
spans: esa clase doble no impediría crear otra en el orden 3. Por eso se añade
un `EXCLUDE` sobre el rango de periodos, que sí lo cubre a nivel de BD.

Revision ID: e9a3b7c2d418
Revises: d6c1f8a390b4
Create Date: 2026-08-15 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e9a3b7c2d418'
down_revision: Union[str, None] = 'd6c1f8a390b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # GiST no sabe comparar uuid/smallint con `=` sin esta extensión.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

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


def downgrade() -> None:
    op.execute("ALTER TABLE class_periods DROP CONSTRAINT class_periods_no_overlap")
    op.drop_constraint("check_span_positive", "class_periods", type_="check")
    op.drop_column("class_periods", "span")
