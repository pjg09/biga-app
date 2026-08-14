"""password_reset_otps: recuperación de contraseña por código OTP

Revision ID: b2f47a1c9d63
Revises: a81c5e07b2f4
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2f47a1c9d63"
down_revision = "a81c5e07b2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_otps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("consumed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("reset_token", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("reset_token_expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("reset_token_used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_password_reset_user", "password_reset_otps", ["user_id", "created_at"])
    op.create_index("idx_password_reset_token", "password_reset_otps", ["reset_token"])


def downgrade() -> None:
    op.drop_index("idx_password_reset_token", table_name="password_reset_otps")
    op.drop_index("idx_password_reset_user", table_name="password_reset_otps")
    op.drop_table("password_reset_otps")
