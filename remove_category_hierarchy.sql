-- Script SQL idempotente para eliminar completamente jerarquías y vision_hint
-- Estado actual (sin columnas de jerarquía)
SELECT
    id,
    name,
    name_en,
    (SELECT COUNT(*) FROM products WHERE category_id = categories.id) as product_count
FROM categories
ORDER BY name;

ALTER TABLE categories DROP COLUMN IF EXISTS parent_id CASCADE;
ALTER TABLE categories DROP COLUMN IF EXISTS level;
ALTER TABLE categories DROP COLUMN IF EXISTS is_leaf;

-- Eliminar vision_hint también
ALTER TABLE categories DROP COLUMN IF EXISTS vision_hint;

-- Eliminar específicamente la categoría padre 'Delantal' si quedó vacía
DELETE FROM categories
WHERE LOWER(name) = 'delantal'
    AND id NOT IN (SELECT DISTINCT category_id FROM products WHERE category_id IS NOT NULL);

-- PASO 6: Verificación final
SELECT
    id,
    name,
    name_en,
    (SELECT COUNT(*) FROM products WHERE category_id = categories.id) as product_count
FROM categories
ORDER BY name;
