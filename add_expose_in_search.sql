-- Agregar campo expose_in_search a product_attribute_config
-- Este campo indica si el atributo debe incluirse en las respuestas de búsqueda

ALTER TABLE product_attribute_config
ADD COLUMN IF NOT EXISTS expose_in_search BOOLEAN DEFAULT false;

-- Actualizar comentario de la tabla
COMMENT ON COLUMN product_attribute_config.expose_in_search IS 'Indica si este atributo debe incluirse en las respuestas del API de búsqueda';

-- Verificar que la columna se agregó correctamente
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'product_attribute_config'
AND column_name = 'expose_in_search';
