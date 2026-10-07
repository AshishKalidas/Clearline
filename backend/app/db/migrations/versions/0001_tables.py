"""Create the Clearline schema."""

from alembic import op

from backend.app.db.models import Base

revision = "0001"
down_revision = "0000"


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE INDEX customers_name_trgm ON customers USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
