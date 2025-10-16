-- Migración: Agregar campos de centroides a tabla categories
-- Fecha: 2025-10-16
-- Sistema: CLIP Comparador V2

-- 1. Agregar columnas para centroides
ALTER TABLE categories 
ADD COLUMN IF NOT EXISTS centroid_embedding TEXT,
ADD COLUMN IF NOT EXISTS centroid_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS centroid_image_count INTEGER DEFAULT 0;

-- 2. Crear índice para consultas rápidas por cliente y centroide
CREATE INDEX IF NOT EXISTS idx_categories_client_centroid 
ON categories(client_id) 
WHERE centroid_embedding IS NOT NULL;

-- 3. Crear función para validar JSON de embeddings
CREATE OR REPLACE FUNCTION validate_embedding_json(embedding_text TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Verificar que sea JSON válido y array
    PERFORM embedding_text::json;
    RETURN json_typeof(embedding_text::json) = 'array';
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- 4. Crear función para calcular centroide automáticamente
CREATE OR REPLACE FUNCTION calculate_category_centroid(category_uuid TEXT)
RETURNS TEXT AS $$
DECLARE
    embedding_count INTEGER := 0;
    centroid_result TEXT;
BEGIN
    -- Esta función será llamada desde Python
    -- Solo valida que la categoría existe y retorna placeholder
    SELECT COUNT(*) INTO embedding_count
    FROM images i
    JOIN products p ON i.product_id = p.id
    WHERE p.category_id = category_uuid 
    AND i.clip_embedding IS NOT NULL 
    AND i.is_processed = true;
    
    -- Si no hay embeddings, retornar NULL
    IF embedding_count = 0 THEN
        RETURN NULL;
    END IF;
    
    -- El cálculo real se hace en Python por performance
    RETURN 'CALCULATE_IN_PYTHON';
END;
$$ LANGUAGE plpgsql;

-- 5. Crear trigger para invalidar centroides cuando cambian imágenes
CREATE OR REPLACE FUNCTION invalidate_category_centroid()
RETURNS TRIGGER AS $$
BEGIN
    -- Cuando se modifica una imagen, invalidar centroide de su categoría
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE categories 
        SET centroid_embedding = NULL,
            centroid_updated_at = NULL,
            centroid_image_count = 0
        WHERE id = (
            SELECT p.category_id 
            FROM products p 
            WHERE p.id = NEW.product_id
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE categories 
        SET centroid_embedding = NULL,
            centroid_updated_at = NULL,
            centroid_image_count = 0
        WHERE id = (
            SELECT p.category_id 
            FROM products p 
            WHERE p.id = OLD.product_id
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 6. Crear trigger en tabla images
DROP TRIGGER IF EXISTS trigger_invalidate_centroid ON images;
CREATE TRIGGER trigger_invalidate_centroid
    AFTER INSERT OR UPDATE OR DELETE ON images
    FOR EACH ROW
    EXECUTE FUNCTION invalidate_category_centroid();

-- 7. Crear vista para estadísticas de centroides
CREATE OR REPLACE VIEW category_centroid_stats AS
SELECT 
    c.id,
    c.name,
    c.client_id,
    c.centroid_embedding IS NOT NULL as has_centroid,
    c.centroid_updated_at,
    c.centroid_image_count,
    COUNT(i.id) as total_images,
    COUNT(CASE WHEN i.clip_embedding IS NOT NULL AND i.is_processed THEN 1 END) as processed_images
FROM categories c
LEFT JOIN products p ON c.id = p.category_id
LEFT JOIN images i ON p.id = i.product_id
WHERE c.is_active = true
GROUP BY c.id, c.name, c.client_id, c.centroid_embedding, c.centroid_updated_at, c.centroid_image_count
ORDER BY c.client_id, c.name;

-- 8. Comentarios de documentación
COMMENT ON COLUMN categories.centroid_embedding IS 'JSON array con embedding centroide precalculado de la categoría';
COMMENT ON COLUMN categories.centroid_updated_at IS 'Timestamp de última actualización del centroide';
COMMENT ON COLUMN categories.centroid_image_count IS 'Número de imágenes usadas para calcular el centroide';

-- 9. Verificar migración
SELECT 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'categories' 
AND column_name IN ('centroid_embedding', 'centroid_updated_at', 'centroid_image_count');

-- Migración completada
SELECT 'Migración de centroides aplicada exitosamente' as status;