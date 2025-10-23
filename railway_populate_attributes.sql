-- Script SQL para poblar atributos de productos en Railway
-- Ejecutar con: python railway_db_tool.py sql -f railway_populate_attributes.sql --yes

-- 1. Primero, verificar si la configuración existe (SKIP seed por ahora)
-- La tabla product_attribute_config aún no tiene la columna optimizer_weight en Railway
-- Se hará después con la migración adecuada

-- 2. Poblar atributos de productos directamente
-- Extraer color del campo 'color' o 'description', asignar marca GOODY, tallas S/M/L

UPDATE products SET 
    attributes = jsonb_build_object(
        'color', COALESCE(
            UPPER(TRIM(color)),  -- Usar campo color si existe
            CASE 
                WHEN UPPER(name) LIKE '%BLANCO%' OR UPPER(name) LIKE '%BLANCA%' OR UPPER(name) LIKE '%WHITE%' THEN 'BLANCA'
                WHEN UPPER(name) LIKE '%NEGRO%' OR UPPER(name) LIKE '%NEGRA%' OR UPPER(name) LIKE '%BLACK%' THEN 'NEGRA'
                WHEN UPPER(name) LIKE '%AZUL%' OR UPPER(name) LIKE '%BLUE%' THEN 'AZUL'
                WHEN UPPER(name) LIKE '%ROJO%' OR UPPER(name) LIKE '%ROJA%' OR UPPER(name) LIKE '%RED%' THEN 'ROJA'
                WHEN UPPER(name) LIKE '%VERDE%' OR UPPER(name) LIKE '%GREEN%' THEN 'VERDE'
                WHEN UPPER(name) LIKE '%ROSA%' OR UPPER(name) LIKE '%PINK%' THEN 'ROSA'
                WHEN UPPER(name) LIKE '%GRIS%' OR UPPER(name) LIKE '%GREY%' THEN 'GRIS'
                WHEN UPPER(name) LIKE '%JEAN%' OR UPPER(name) LIKE '%DENIM%' THEN 'JEAN'
                WHEN UPPER(description) LIKE '%BLANCO%' OR UPPER(description) LIKE '%BLANCA%' OR UPPER(description) LIKE '%WHITE%' THEN 'BLANCA'
                WHEN UPPER(description) LIKE '%NEGRO%' OR UPPER(description) LIKE '%NEGRA%' OR UPPER(description) LIKE '%BLACK%' THEN 'NEGRA'
                WHEN UPPER(description) LIKE '%AZUL%' OR UPPER(description) LIKE '%BLUE%' THEN 'AZUL'
                ELSE NULL
            END
        ),
        'marca', 'GOODY',
        'talla', ARRAY['S', 'M', 'L']::text[]  -- Asignar tallas S, M, L por defecto
    )
WHERE client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
  AND (attributes IS NULL OR attributes = '{}'::jsonb);

-- 3. Verificar resultados
SELECT 
    name,
    sku,
    color as color_columna,
    attributes->>'color' as color_atributo,
    attributes->>'marca' as marca,
    attributes->'talla' as tallas,
    attributes
FROM products 
WHERE client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0'
ORDER BY name
LIMIT 10;
