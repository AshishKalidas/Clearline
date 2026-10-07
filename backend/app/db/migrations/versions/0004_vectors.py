"""Build cosine IVFFlat indexes for each local retrieval corpus."""

from alembic import op

revision = "0004"
down_revision = "0001"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table, column in [
            ("resolved_cases", "embedding"),
            ("customers", "notes_embedding"),
            ("runbook_chunks", "embedding"),
        ]:
            op.execute(
                f"CREATE INDEX {table}_cosine ON {table} USING ivfflat "
                f"({column} vector_cosine_ops) WITH (lists = 10)"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("resolved_cases", "customers", "runbook_chunks"):
            op.execute(f"DROP INDEX {table}_cosine")
