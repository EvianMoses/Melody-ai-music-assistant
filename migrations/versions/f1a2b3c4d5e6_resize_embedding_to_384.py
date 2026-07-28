"""Resize knowledge_chunks.embedding to 384 dims (multilingual-e5-small)

Selected retrieval model is intfloat/multilingual-e5-small (384-d) per
docs/adr/ADR-003-embedding-model.md. All embeddings are currently NULL, so the
column type change is safe; the HNSW index is dropped and recreated around it.

Revision ID: f1a2b3c4d5e6
Revises: dc82e50ee3c9
Create Date: 2026-07-24 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "dc82e50ee3c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HNSW_WITH = {"m": 16, "ef_construction": 64}
_HNSW_OPS = {"embedding": "vector_cosine_ops"}


def upgrade() -> None:
    """Shrink the embedding vector from 768 to 384 dimensions."""
    op.drop_index(
        "ix_knowledge_chunks_embedding_hnsw",
        table_name="knowledge_chunks",
        postgresql_using="hnsw",
        postgresql_with=_HNSW_WITH,
        postgresql_ops=_HNSW_OPS,
    )
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(384)")
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with=_HNSW_WITH,
        postgresql_ops=_HNSW_OPS,
    )


def downgrade() -> None:
    """Restore the 768-dimension embedding vector."""
    op.drop_index(
        "ix_knowledge_chunks_embedding_hnsw",
        table_name="knowledge_chunks",
        postgresql_using="hnsw",
        postgresql_with=_HNSW_WITH,
        postgresql_ops=_HNSW_OPS,
    )
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(768)")
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with=_HNSW_WITH,
        postgresql_ops=_HNSW_OPS,
    )
