-- Migración: Crear tabla color_mappings para sistema de aprendizaje de colores
-- Permite que cada cliente tenga su propia paleta de colores aprendida automáticamente.
-- Crear tabla color_mappings
CREATE TABLE IF NOT EXISTS color_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    raw_color VARCHAR(100) NOT NULL,
    normalized_color VARCHAR(50),
    similarity_group VARCHAR(50),
    usage_count INTEGER NOT NULL DEFAULT 1,
    confidence FLOAT,
    extra_metadata JSONB DEFAULT '{}',
    last_used_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_client_raw_color UNIQUE(client_id, raw_color)
);

-- Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_color_mappings_client ON color_mappings(client_id);
CREATE INDEX IF NOT EXISTS idx_color_mappings_usage ON color_mappings(client_id, usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_color_mappings_group ON color_mappings(client_id, similarity_group);

-- Comentarios para documentación
COMMENT ON TABLE color_mappings IS 'Sistema de aprendizaje automático de colores por cliente';
COMMENT ON COLUMN color_mappings.raw_color IS 'Color tal como está en el producto (ej: "coral vibrante")';
COMMENT ON COLUMN color_mappings.normalized_color IS 'Color normalizado por LLM (ej: "CORAL")';
COMMENT ON COLUMN color_mappings.similarity_group IS 'Grupo de similitud (ej: "NARANJA")';
COMMENT ON COLUMN color_mappings.usage_count IS 'Contador de veces que se ha usado este color';
COMMENT ON COLUMN color_mappings.confidence IS 'Confianza del LLM al normalizar (0.0 a 1.0)';
COMMENT ON COLUMN color_mappings.extra_metadata IS 'Metadatos adicionales (ej: {"source": "manual", "hex": "#FF7F50"})';
