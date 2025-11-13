-- Drop experimental/conditional calibration and training tables
-- Safe in production: use IF EXISTS and CASCADE to remove dependent objects

BEGIN;

DROP TABLE IF EXISTS training_images CASCADE;
DROP TABLE IF EXISTS calibration_runs CASCADE;
DROP TABLE IF EXISTS training_events CASCADE;
DROP TABLE IF EXISTS client_category_variants CASCADE;

COMMIT;
