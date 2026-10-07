"""Create least-privilege demo roles and enforce append-only audit storage."""

from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clearline_app') THEN
        CREATE ROLE clearline_app LOGIN PASSWORD 'local-app-only';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clearline_agent') THEN
        CREATE ROLE clearline_agent LOGIN PASSWORD 'local-agent-only';
      END IF;
    END $$""")
    op.execute("GRANT clearline_agent TO clearline_app")
    op.execute("GRANT USAGE ON SCHEMA public TO clearline_app, clearline_agent")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO clearline_app, clearline_agent")
    op.execute("GRANT INSERT ON proposals, audit_events TO clearline_agent")
    for table in (
        "customers",
        "invoices",
        "bank_lines",
        "allocations",
        "proposals",
        "resolved_cases",
        "runbook_chunks",
        "pop_documents",
    ):
        op.execute(f"GRANT INSERT, UPDATE, DELETE ON {table} TO clearline_app")
    op.execute("GRANT INSERT ON audit_events TO clearline_app")
    op.execute("ALTER ROLE clearline_agent SET statement_timeout = '5s'")
    op.execute("""CREATE FUNCTION immutable_audit() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'audit_events are append-only'; END $$""")
    op.execute(
        "CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION immutable_audit()"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_append_only ON audit_events")
        op.execute("DROP FUNCTION immutable_audit()")
