"""demo_leads: solicitudes de demo de la landing pública

Revision ID: f6d9a4c30e18
Revises: e5b3f8c210a7
Create Date: 2026-08-10

Tabla deliberadamente sin `institution_id`: un visitante que pide una demo no
pertenece todavía a ninguna institución. Ver `docs/database-schema.md`.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6d9a4c30e18"
down_revision = "e5b3f8c210a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `notification_status` ya existe (lo creó la migración inicial para
    # notifications_log). create_type=False evita que Postgres falle al
    # intentar recrearlo.
    notification_status = postgresql.ENUM(
        "PENDING", "SENT", "FAILED", name="notification_status", create_type=False
    )

    op.create_table(
        "demo_leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="LANDING_CTA"),
        sa.Column(
            "notification_status", notification_status, nullable=False, server_default="PENDING"
        ),
        sa.Column("notification_error", sa.Text(), nullable=True),
        sa.Column("notified_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_demo_leads_created", "demo_leads", ["created_at"])
    op.create_index("idx_demo_leads_email_created", "demo_leads", ["email", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_demo_leads_email_created", table_name="demo_leads")
    op.drop_index("idx_demo_leads_created", table_name="demo_leads")
    op.drop_table("demo_leads")
    # No se borra el tipo `notification_status`: notifications_log sigue usándolo.
