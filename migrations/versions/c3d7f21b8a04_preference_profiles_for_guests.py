"""Let a guest own a preference profile (Phase 7 §7.2, PERS-003).

`user_preferences` is already the materialized versioned profile table, but
`user_id` was NOT NULL — so only signed-in people could have one. Feedback from
a guest is still feedback, and requiring an account before the app learns
anything would leave every first session permanently unpersonalized.

Three changes:
  * `user_id` becomes nullable;
  * `guest_session_id` is added, mirroring how `feedback_events` already
    identifies a guest;
  * a CHECK enforces exactly one owner, so a row with both ids or neither
    cannot exist. Without it "whose profile is this?" stops having an answer,
    and the merge-on-sign-in path (`merge_guest_into_user`) would have no
    reliable way to find the guest's rows.

Revision ID: c3d7f21b8a04
Revises: b8e4f1a92c37
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d7f21b8a04"
down_revision = "b8e4f1a92c37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_preferences",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "user_preferences",
        sa.Column("guest_session_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    )
    op.create_foreign_key(
        "fk_user_preferences_guest_session_id",
        "user_preferences",
        "guest_sessions",
        ["guest_session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_user_preferences_guest_session_id",
        "user_preferences",
        ["guest_session_id"],
    )
    op.create_unique_constraint(
        "uq_user_preferences_guest_version",
        "user_preferences",
        ["guest_session_id", "version"],
    )
    op.create_check_constraint(
        "ck_user_preferences_single_owner",
        "user_preferences",
        "(user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_preferences_single_owner", "user_preferences", type_="check")
    op.drop_constraint("uq_user_preferences_guest_version", "user_preferences", type_="unique")
    op.drop_index("ix_user_preferences_guest_session_id", table_name="user_preferences")
    op.drop_constraint(
        "fk_user_preferences_guest_session_id", "user_preferences", type_="foreignkey"
    )
    op.drop_column("user_preferences", "guest_session_id")
    # Rows created for guests have no user_id, so restoring NOT NULL would fail
    # on real data. They are deleted first: a downgrade to a schema that cannot
    # represent them has to say what happens to them, and silently failing the
    # migration is worse than removing rows the old schema never supported.
    op.execute("DELETE FROM user_preferences WHERE user_id IS NULL")
    op.alter_column(
        "user_preferences",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
