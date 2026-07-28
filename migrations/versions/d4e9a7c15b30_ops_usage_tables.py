"""Operations tables for WF-008 monitoring and budget (N8N-REAL-004).

WF-008 is specified to read *real* usage and health. Two of the four things it
must read had nowhere to be read from:

  * **Provider quota** was recorded only as a log line, so the one hard
    operational limit in this system (YouTube's 10,000 units/day) was visible to
    a human tailing `docker logs` and to nothing else.
  * **The daily summary** WF-008 is supposed to store had no destination.

`model_usage` already existed from the Phase 2 schema and needed no change here
— it simply had no writer until this revision's companion service code.

Both tables are additive: nothing existing is altered, so this migration cannot
affect a running request path.

Revision ID: d4e9a7c15b30
Revises: c3d7f21b8a04
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e9a7c15b30"
down_revision = "c3d7f21b8a04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_quota_usage",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_quota_usage_created_at", "provider_quota_usage", ["created_at"]
    )
    op.create_index(
        "ix_provider_quota_usage_provider_method",
        "provider_quota_usage",
        ["provider", "method"],
    )

    op.create_table(
        "ops_daily_summary",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("summary_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("budget_percent", sa.Float(), nullable=True),
        sa.Column(
            "alert_level",
            sa.String(length=16),
            server_default=sa.text("'ok'"),
            nullable=False,
        ),
        sa.Column(
            "alert_sent",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Unique so a re-run of the daily schedule updates the day instead of
        # appending a second row that disagrees with the first about whether a
        # budget threshold was crossed. WF-008's upsert depends on this.
        sa.UniqueConstraint("summary_date", name="uq_ops_daily_summary_date"),
    )
    op.create_index("ix_ops_daily_summary_date", "ops_daily_summary", ["summary_date"])


def downgrade() -> None:
    op.drop_index("ix_ops_daily_summary_date", table_name="ops_daily_summary")
    op.drop_table("ops_daily_summary")
    op.drop_index(
        "ix_provider_quota_usage_provider_method", table_name="provider_quota_usage"
    )
    op.drop_index(
        "ix_provider_quota_usage_created_at", table_name="provider_quota_usage"
    )
    op.drop_table("provider_quota_usage")
