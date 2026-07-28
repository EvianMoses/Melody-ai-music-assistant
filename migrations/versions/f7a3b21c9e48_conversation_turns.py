"""Conversational memory (agent redesign).

Melody had no conversation. Every message was an independent recommendation
request, which produced three user-visible failures:

  * a correction ("Coldplay is not a new artist") was embedded as a SEARCH QUERY
    and returned more Coldplay;
  * a meta-question ("what was my last question?") matched the word "last"
    lexically and returned a track called "Last Last";
  * and there was no way to tell whether memory worked, because there was none.

This table is the storage half of the fix. Owner is user OR guest, never both --
the same nullable-owner + CHECK pattern `user_preferences` already uses, and for
the same reason: someone who has not signed in still holds a conversation.

Revision ID: f7a3b21c9e48
Revises: e5f1c48a9d72
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f7a3b21c9e48"
down_revision = "e5f1c48a9d72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_turns",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("guest_session_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("turn_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["guest_session_id"], ["guest_sessions.id"], ondelete="CASCADE"
        ),
        # Exactly one owner. Without it, "whose conversation is this?" stops
        # having an answer -- and the guest-to-user merge on sign-in would have
        # no reliable way to find a guest's turns.
        sa.CheckConstraint(
            "(user_id IS NOT NULL) <> (guest_session_id IS NOT NULL)",
            name="ck_conversation_turns_single_owner",
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_conversation_turns_role"
        ),
    )
    # Composite indexes: every read is "the last N turns for this owner, in
    # order", so ordering belongs in the index rather than in a sort.
    op.create_index(
        "ix_conversation_turns_user_id", "conversation_turns", ["user_id", "turn_index"]
    )
    op.create_index(
        "ix_conversation_turns_guest_id",
        "conversation_turns",
        ["guest_session_id", "turn_index"],
    )
    op.create_index(
        "ix_conversation_turns_created_at", "conversation_turns", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_turns_created_at", table_name="conversation_turns")
    op.drop_index("ix_conversation_turns_guest_id", table_name="conversation_turns")
    op.drop_index("ix_conversation_turns_user_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")
