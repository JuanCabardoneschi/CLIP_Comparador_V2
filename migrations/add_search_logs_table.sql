-- Migración: Sistema de Analytics de Uso
-- Fecha: 2025-11-26
-- Propósito: Tracking de búsquedas para analytics y gap detection

-- Crear tabla search_logs
CREATE TABLE IF NOT EXISTS search_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) NOT NULL,

    -- Tipo y datos de búsqueda
    search_type VARCHAR(20) NOT NULL,  -- 'visual', 'text', 'gpt4v-unified'
    query_text TEXT,                    -- Query original (si es texto)
    image_url TEXT,                     -- URL de imagen (si es visual)

    -- Categorías detectadas
    categories_detected TEXT[],         -- Categorías que GPT-4V/sistema detectó
    categories_matched TEXT[],          -- Categorías que SÍ existen en el catálogo
    categories_missing TEXT[],          -- Categorías detectadas pero NO existen

    -- Términos en búsqueda por texto
    terms_extracted TEXT[],             -- Términos extraídos de la query
    terms_matched TEXT[],               -- Términos que matchearon con catálogo
    terms_unmatched TEXT[],             -- Términos que NO matchearon (GAP)

    -- Resultados
    results_count INTEGER DEFAULT 0,
    had_results BOOLEAN DEFAULT FALSE,

    -- Performance
    response_time_ms INTEGER,

    -- Metadata
    threshold_used FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para queries rápidas
CREATE INDEX IF NOT EXISTS idx_search_logs_client_date
    ON search_logs(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_logs_categories_missing
    ON search_logs USING GIN(categories_missing);

CREATE INDEX IF NOT EXISTS idx_search_logs_terms_unmatched
    ON search_logs USING GIN(terms_unmatched);

CREATE INDEX IF NOT EXISTS idx_search_logs_type
    ON search_logs(search_type);

-- Función para limpiar logs antiguos (60 días)
CREATE OR REPLACE FUNCTION cleanup_old_search_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM search_logs
    WHERE created_at < NOW() - INTERVAL '60 days';
END;
$$ LANGUAGE plpgsql;

-- Comentarios
COMMENT ON TABLE search_logs IS 'Logs de búsquedas para analytics y gap detection';
COMMENT ON COLUMN search_logs.categories_missing IS 'Categorías que usuarios buscan pero no existen en catálogo';
COMMENT ON COLUMN search_logs.terms_unmatched IS 'Términos de búsqueda por texto que no matchean con vocabulario';
