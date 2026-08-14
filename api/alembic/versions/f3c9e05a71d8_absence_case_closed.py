"""attendance_records.absence_closed_at: cierre del caso de inasistencia

Revision ID: f3c9e05a71d8
Revises: e2a7d1b48c95
Create Date: 2026-08-14

No se llama `archived_at` a propósito: el registro de asistencia sigue contando
en el roster, en la toma de lista y en las estadísticas. Lo único que se cierra
es el seguimiento del docente en la sección "Inasistencias".
"""

from alembic import op
import sqlalchemy as sa

revision = "f3c9e05a71d8"
down_revision = "e2a7d1b48c95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attendance_records",
        sa.Column("absence_closed_at", sa.TIMESTAMP(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("attendance_records", "absence_closed_at")
