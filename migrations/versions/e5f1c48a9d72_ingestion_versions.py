"""Staged ingestion versions (RAG-010).

§1.10's rule is "do not publish a new ingestion version until smoke queries
pass", and that only means something if a version can exist WITHOUT being live.
Until now ingestion deleted the document and re-inserted it, so a bad chunking
change was live the instant it was written and the only way back was to
re-ingest from source and hope.

This table gives a version a lifecycle: staged -> active -> superseded, or
staged -> rolled_back. Retrieval reads the active version and no other, so a
staged version is invisible to users until published -- which is what turns
WF-007's smoke-query step into a gate rather than a report.

The partial unique index is the load-bearing part: **at most one row may be
active**, enforced by PostgreSQL rather than by whichever code path happens to
publish. Two active versions would make "what did retrieval actually search?"
unanswerable.

The data migration seeds the corpus that already exists (`v0-text-2026-07`) as
active, so retrieval keeps working the moment the version filter goes live. A
migration that left zero active versions would take the whole product down.

Revision ID: e5f1c48a9d72
Revises: d4e9a7c15b30
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5f1c48a9d72"
down_revision = "d4e9a7c15b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_versions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'staged'"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("version", name="uq_ingestion_versions_version"),
    )
    op.create_index("ix_ingestion_versions_status", "ingestion_versions", ["status"])
    # At most one active version, enforced by the database.
    op.create_index(
        "uq_ingestion_versions_single_active",
        "ingestion_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # Seed whatever is already in knowledge_chunks as the active version, so the
    # version filter has something to match the instant it goes live.
    op.execute(
        """
        INSERT INTO ingestion_versions (version, status, published_at, stats, notes)
        SELECT
            kc.ingestion_version,
            'active',
            now(),
            jsonb_build_object(
                'chunks', count(*),
                'embedded', count(kc.embedding),
                'seeded_by_migration', true
            ),
            'Seeded by migration e5f1c48a9d72 from the corpus already in place.'
        FROM knowledge_chunks kc
        GROUP BY kc.ingestion_version
        ORDER BY count(*) DESC
        LIMIT 1
        """
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_versions_single_active", table_name="ingestion_versions")
    op.drop_index("ix_ingestion_versions_status", table_name="ingestion_versions")
    op.drop_table("ingestion_versions")
