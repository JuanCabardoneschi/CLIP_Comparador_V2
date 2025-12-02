-- PostgreSQL schema changes for Tiendanube integration
-- Use with local_db_tool.py or railway_db_tool.py

-- clients extensions
ALTER TABLE clients ADD COLUMN IF NOT EXISTS integration_type VARCHAR(50) DEFAULT 'standalone' NOT NULL;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS integration_config JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_read_only BOOLEAN DEFAULT FALSE NOT NULL;

-- tiendanube_integrations
CREATE TABLE IF NOT EXISTS tiendanube_integrations (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    store_id VARCHAR(50) NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    store_name VARCHAR(255),
    store_email VARCHAR(255),
    store_domain VARCHAR(255),
    scopes TEXT[],
    script_id INTEGER,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    installed_at TIMESTAMP,
    uninstalled_at TIMESTAMP,
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50),
    sync_error TEXT,
    webhook_ids JSONB
);
CREATE INDEX IF NOT EXISTS ix_tn_integrations_store_id ON tiendanube_integrations(store_id);
CREATE INDEX IF NOT EXISTS ix_tn_integrations_client_id ON tiendanube_integrations(client_id);

-- products extensions
ALTER TABLE products ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS external_variant_id VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS external_url TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP;
ALTER TABLE products ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'synced';
CREATE INDEX IF NOT EXISTS ix_products_external_id ON products(external_id);
CREATE INDEX IF NOT EXISTS ix_products_sync_status ON products(sync_status);

-- categories extensions
ALTER TABLE categories ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);
ALTER TABLE categories ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'synced';
CREATE INDEX IF NOT EXISTS ix_categories_external_id ON categories(external_id);

-- images Base64 extensions
ALTER TABLE images ADD COLUMN IF NOT EXISTS base64_data TEXT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS base64_thumb TEXT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS mime_type VARCHAR(50);
ALTER TABLE images ADD COLUMN IF NOT EXISTS width INT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS height INT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS size_bytes INT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS hash_sha256 VARCHAR(128);
ALTER TABLE images ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE images ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMP;
ALTER TABLE images ADD COLUMN IF NOT EXISTS clip_embedding TEXT;

-- sync_logs
CREATE TABLE IF NOT EXISTS sync_logs (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    sync_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100),
    action VARCHAR(50),
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    metadata JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_sync_logs_client_id ON sync_logs(client_id);
CREATE INDEX IF NOT EXISTS ix_sync_logs_created_at ON sync_logs(created_at);
CREATE INDEX IF NOT EXISTS ix_sync_logs_status ON sync_logs(status);
