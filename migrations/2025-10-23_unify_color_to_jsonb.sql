-- Unify color into JSONB attributes and prepare indexes

BEGIN;

-- 1) Backfill: copy Product.color to attributes->'color' if missing
UPDATE products
SET attributes = jsonb_set(
  COALESCE(attributes, '{}'::jsonb),
  '{color}',
  to_jsonb(UPPER(TRIM(color)))
)
WHERE color IS NOT NULL
  AND (attributes IS NULL OR attributes ? 'color' = FALSE OR NULLIF(TRIM(attributes->>'color'), '') IS NULL);

-- 2) Optional: normalize existing JSONB 'color' to uppercase (idempotent)
UPDATE products
SET attributes = jsonb_set(
  attributes,
  '{color}',
  to_jsonb(UPPER(TRIM(attributes->>'color')))
)
WHERE attributes ? 'color';

-- 3) Create expression indexes for fast lookups by color
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_products_color_jsonb'
  ) THEN
    EXECUTE 'CREATE INDEX idx_products_color_jsonb ON products ((UPPER(TRIM(attributes->>''color''))))';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_products_client_cat_color_jsonb'
  ) THEN
    EXECUTE 'CREATE INDEX idx_products_client_cat_color_jsonb ON products (client_id, category_id, (UPPER(TRIM(attributes->>''color''))))';
  END IF;
END$$;

COMMIT;

-- 4) (Later) Drop column when code no longer references it:
-- ALTER TABLE products DROP COLUMN color;
