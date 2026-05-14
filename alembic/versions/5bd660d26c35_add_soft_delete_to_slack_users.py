"""add soft delete to slack_users

Revision ID: 5bd660d26c35
Revises: f3548701d448
Create Date: 2026-05-12 13:58:39.144152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bd660d26c35'
down_revision: Union[str, None] = 'f3548701d448'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "slack_users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "slack_users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_slack_users_tenant_active",
        "slack_users",
        ["tenant_id", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_slack_users_tenant_active", table_name="slack_users")
    op.drop_column("slack_users", "deleted_at")
    op.drop_column("slack_users", "is_deleted")