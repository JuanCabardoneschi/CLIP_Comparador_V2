-- Agregar columna manage_stock a products (WooCommerce: stock gestionado vs ilimitado)
ALTER TABLE products
ADD COLUMN IF NOT EXISTS manage_stock BOOLEAN DEFAULT TRUE;

-- Asegurar valores no nulos en registros existentes
UPDATE products
SET manage_stock = TRUE
WHERE manage_stock IS NULL;
