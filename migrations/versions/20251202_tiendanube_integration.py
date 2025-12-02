"""
Alembic revision for Tiendanube integration: clients extensions,
tiendanube_integrations, products/categories/images extensions, sync_logs.

If Alembic causes issues in your environment, you can run the SQL blocks
in upgrade() directly using `local_db_tool.py` or `railway_db_tool.py`.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251202_tn_integration"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # clients extensions
    op.add_column(
        "clients",
        sa.Column("integration_type", sa.String(length=50), nullable=False, server_default="standalone"),
    )
    op.add_column(
        "clients",
        sa.Column("integration_config", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "clients",
        sa.Column("is_read_only", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    # optional defaults already exist; keep minimal change

    # tiendanube_integrations
    op.create_table(
        "tiendanube_integrations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", sa.String(length=50), nullable=False, unique=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("store_name", sa.String(length=255), nullable=True),
        sa.Column("store_email", sa.String(length=255), nullable=True),
        sa.Column("store_domain", sa.String(length=255), nullable=True),
        sa.Column("scopes", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("script_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("installed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("uninstalled_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("last_sync_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("sync_status", sa.String(length=50), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("webhook_ids", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tn_integrations_store_id", "tiendanube_integrations", ["store_id"])
    op.create_index("ix_tn_integrations_client_id", "tiendanube_integrations", ["client_id"])

    # products extensions
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("external_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("external_variant_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("external_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_sync_at", sa.TIMESTAMP(), nullable=True))
        batch.add_column(sa.Column("sync_status", sa.String(length=50), nullable=True, server_default="synced"))
    op.create_index("ix_products_external_id", "products", ["external_id"])
    op.create_index("ix_products_sync_status", "products", ["sync_status"])

    # categories extensions
    with op.batch_alter_table("categories") as batch:
        batch.add_column(sa.Column("external_id", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("last_sync_at", sa.TIMESTAMP(), nullable=True))
        batch.add_column(sa.Column("sync_status", sa.String(length=50), nullable=True, server_default="synced"))
    op.create_index("ix_categories_external_id", "categories", ["external_id"])

    # images Base64 extensions
    with op.batch_alter_table("images") as batch:
        batch.add_column(sa.Column("base64_data", sa.Text(), nullable=True))
        batch.add_column(sa.Column("base64_thumb", sa.Text(), nullable=True))
        batch.add_column(sa.Column("mime_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("width", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("height", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("hash_sha256", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source_updated_at", sa.TIMESTAMP(), nullable=True))
        batch.add_column(sa.Column("clip_embedding", sa.Text(), nullable=True))

    # sync_logs
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sync_logs_client_id", "sync_logs", ["client_id"])
    op.create_index("ix_sync_logs_created_at", "sync_logs", ["created_at"])
    op.create_index("ix_sync_logs_status", "sync_logs", ["status"])


def downgrade():
    # drop sync_logs
    op.drop_index("ix_sync_logs_status", table_name="sync_logs")
    op.drop_index("ix_sync_logs_created_at", table_name="sync_logs")
    op.drop_index("ix_sync_logs_client_id", table_name="sync_logs")
    op.drop_table("sync_logs")

    # images extensions
    with op.batch_alter_table("images") as batch:
        for col in [
            "base64_data",
            "base64_thumb",
            "mime_type",
            "width",
            "height",
            "size_bytes",
            "hash_sha256",
            "source_url",
            "source_updated_at",
            "clip_embedding",
        ]:
            batch.drop_column(col)

    # categories extensions
    op.drop_index("ix_categories_external_id", table_name="categories")
    with op.batch_alter_table("categories") as batch:
        batch.drop_column("external_id")
        batch.drop_column("last_sync_at")
        batch.drop_column("sync_status")

    # products extensions
    op.drop_index("ix_products_sync_status", table_name="products")
    op.drop_index("ix_products_external_id", table_name="products")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("external_id")
        batch.drop_column("external_variant_id")
        batch.drop_column("external_url")
        batch.drop_column("last_sync_at")
        batch.drop_column("sync_status")

    # tiendanube_integrations
    op.drop_index("ix_tn_integrations_client_id", table_name="tiendanube_integrations")
    op.drop_index("ix_tn_integrations_store_id", table_name="tiendanube_integrations")
    op.drop_table("tiendanube_integrations")

    # clients extensions
    op.drop_column("clients", "is_read_only")
    op.drop_column("clients", "integration_config")
    op.drop_column("clients", "integration_type")
