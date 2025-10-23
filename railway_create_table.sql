-- Script para crear tabla store_search_config en Railway PostgreSQL
-- Ejecutar MANUALMENTE en Railway PostgreSQL Query editor

-- Verificar si la tabla ya existe
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'store_search_config'
);

-- Si devuelve 'f' (false), ejecutar el CREATE TABLE:

CREATE TABLE IF NOT EXISTS store_search_config (
    store_id UUID PRIMARY KEY,
    visual_weight FLOAT NOT NULL DEFAULT 0.6,
    metadata_weight FLOAT NOT NULL DEFAULT 0.3,
    business_weight FLOAT NOT NULL DEFAULT 0.1,
    metadata_config JSONB NOT NULL DEFAULT '{"color_weight": 1.0, "brand_weight": 1.0, "pattern_weight": 0.8, "material_weight": 0.7, "style_weight": 0.6}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    CONSTRAINT fk_store_search_config_client
        FOREIGN KEY (store_id)
        REFERENCES clients(id)
        ON DELETE CASCADE
);

-- Crear índice para mejorar performance
CREATE INDEX IF NOT EXISTS idx_store_search_config_store_id
ON store_search_config(store_id);

-- Verificar que se creó correctamente
\d store_search_config;

-- Insertar configuración default para clientes existentes
INSERT INTO store_search_config (store_id, visual_weight, metadata_weight, business_weight)
SELECT
    id,
    0.6,
    0.3,
    0.1
FROM clients
WHERE id NOT IN (SELECT store_id FROM store_search_config)
ON CONFLICT (store_id) DO NOTHING;

-- Verificar datos insertados
SELECT
    c.name as client_name,
    ssc.visual_weight,
    ssc.metadata_weight,
    ssc.business_weight,
    ssc.created_at
FROM store_search_config ssc
JOIN clients c ON c.id = ssc.store_id
ORDER BY c.name;
