"""el bloque horario exige docente

Hasta ahora un docente asignado a un salón veía **todas** las horas de ese salón
como suyas: Asistencia unía `ClassPeriod → UserGroup` por salón, no por bloque.
Con 3 docentes en Once A, los 3 veían las 6 clases del día.

Al pasar a filtrar por `class_periods.user_id`, un bloque sin docente quedaría
sin nadie que tome lista — y si fuese primera hora, **no se dispararía la
notificación de inasistencia al acudiente**. Por eso la columna pasa a NOT NULL:
la regla "todo bloque tiene docente" es lo que hace segura la otra mitad.

Backfill determinista antes de la restricción: a cada bloque se le asigna un
docente de `user_groups` de su salón, prefiriendo rol TEACHER y desempatando por
nombre. Es una elección arbitraria cuando el salón tiene varios — el admin la
corrige en la rejilla, que ahora existe justamente para eso.

Revision ID: d6c1f8a390b4
Revises: c5b9e2f47a13
Create Date: 2026-08-15 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd6c1f8a390b4'
down_revision: Union[str, None] = 'c5b9e2f47a13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        UPDATE class_periods cp
        SET user_id = sub.user_id
        FROM (
            SELECT DISTINCT ON (ug.group_id) ug.group_id, ug.user_id
            FROM user_groups ug
            JOIN users u ON u.id = ug.user_id
            WHERE u.is_active
            ORDER BY ug.group_id, (u.role::text = 'TEACHER') DESC, u.first_name, u.last_name
        ) sub
        WHERE cp.group_id = sub.group_id AND cp.user_id IS NULL
    """))

    # Si queda alguno sin docente, es porque su salón no tiene ningún docente
    # asignado. Se falla con un mensaje claro en vez de dejar que el ALTER
    # reviente con un error de Postgres que no dice qué arreglar.
    huerfanos = conn.execute(sa.text("""
        SELECT count(*) FROM class_periods WHERE user_id IS NULL
    """)).scalar_one()
    if huerfanos:
        raise RuntimeError(
            f"{huerfanos} bloques horarios sin docente y sin ningún docente asignado a su "
            "salón. Asigna un docente al salón (Horarios › Docentes por salón) y reintenta."
        )

    op.alter_column("class_periods", "user_id", existing_type=sa.UUID(), nullable=False)


def downgrade() -> None:
    op.alter_column("class_periods", "user_id", existing_type=sa.UUID(), nullable=True)
