-- Drop legacy products.color column after migrating to JSONB attributes
BEGIN;
ALTER TABLE products DROP COLUMN IF EXISTS color;
COMMIT;
