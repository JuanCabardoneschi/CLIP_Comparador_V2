-- Migración: Crear tabla woocommerce_integrations
-- Descripción: Tabla para almacenar integraciones con WooCommerce
-- Fecha: 2026-01-14

-- Crear tabla woocommerce_integrations
CREATE TABLE IF NOT EXISTS woocommerce_integrations (
    -- Identificadores
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,

    -- Datos de la tienda WooCommerce
    store_url VARCHAR(500) NOT NULL UNIQUE,
    store_name VARCHAR(255),
    store_email VARCHAR(255),

    -- Credenciales REST API (encriptadas)
    consumer_key TEXT NOT NULL,
    consumer_secret TEXT NOT NULL,

    -- Configuración de API
    api_version VARCHAR(10) NOT NULL DEFAULT 'v3',
    use_ssl BOOLEAN NOT NULL DEFAULT TRUE,

    -- Webhooks
    webhook_ids JSONB,
    webhook_secret VARCHAR(100),

    -- Método de instalación del widget
    widget_method VARCHAR(50),

    -- Estado
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    installed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uninstalled_at TIMESTAMP,

    -- Sincronización
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50),
    sync_error TEXT,

    -- Metadatos
    wc_version VARCHAR(20),
    wp_version VARCHAR(20),
    timezone VARCHAR(50),
    currency VARCHAR(10),

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Restricciones
    CONSTRAINT fk_woocommerce_integrations_client_id
        FOREIGN KEY (client_id)
        REFERENCES clients(id)
        ON DELETE CASCADE
);

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_woocommerce_integrations_client_id
    ON woocommerce_integrations(client_id);

CREATE INDEX IF NOT EXISTS idx_woocommerce_integrations_store_url
    ON woocommerce_integrations(store_url);

CREATE INDEX IF NOT EXISTS idx_woocommerce_integrations_is_active
    ON woocommerce_integrations(is_active);

-- Comentarios para documentación
COMMENT ON TABLE woocommerce_integrations IS
'Tabla para almacenar integraciones con tiendas WooCommerce. Cada registro representa una tienda conectada a través de REST API';

COMMENT ON COLUMN woocommerce_integrations.consumer_key IS
'Consumer Key encriptado para autenticación REST API de WooCommerce (ck_...)';

COMMENT ON COLUMN woocommerce_integrations.consumer_secret IS
'Consumer Secret encriptado para autenticación REST API de WooCommerce (cs_...)';

COMMENT ON COLUMN woocommerce_integrations.webhook_ids IS
'JSONB con IDs de webhooks registrados, ej: {"product.created": 123, "product.updated": 124}';

COMMENT ON COLUMN woocommerce_integrations.sync_status IS
'Estado de sincronización: pending, in_progress, completed, error';
