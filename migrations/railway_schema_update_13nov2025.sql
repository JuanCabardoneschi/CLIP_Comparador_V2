-- ================================================================
-- MIGRACIÓN RAILWAY: Eliminación Jerarquías + Adición vision_hint
-- Fecha: 13 Noviembre 2025
-- Autor: Sistema CLIP Comparador V2
-- ================================================================

BEGIN;

-- PASO 1: Agregar vision_hint a categories (si no existe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'vision_hint'
    ) THEN
        ALTER TABLE categories ADD COLUMN vision_hint TEXT;
        RAISE NOTICE 'Columna vision_hint agregada';
    ELSE
        RAISE NOTICE 'Columna vision_hint ya existe';
    END IF;
END $$;

-- PASO 2: Eliminar columnas de jerarquía de categories
DO $$
BEGIN
    -- Eliminar parent_id (incluyendo constraint FK si existe)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'parent_id'
    ) THEN
        -- Primero eliminar FK constraint si existe
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_parent_id_fkey;
        ALTER TABLE categories DROP COLUMN parent_id;
        RAISE NOTICE 'Columna parent_id eliminada';
    END IF;

    -- Eliminar level
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'level'
    ) THEN
        ALTER TABLE categories DROP COLUMN level;
        RAISE NOTICE 'Columna level eliminada';
    END IF;

    -- Eliminar is_leaf
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'is_leaf'
    ) THEN
        ALTER TABLE categories DROP COLUMN is_leaf;
        RAISE NOTICE 'Columna is_leaf eliminada';
    END IF;
END $$;

-- PASO 3: Agregar name_en a categories si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'name_en'
    ) THEN
        ALTER TABLE categories ADD COLUMN name_en VARCHAR(100);
        RAISE NOTICE 'Columna name_en agregada a categories';
    END IF;
END $$;

-- PASO 4: Agregar name_en a products si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'name_en'
    ) THEN
        ALTER TABLE products ADD COLUMN name_en VARCHAR(200);
        RAISE NOTICE 'Columna name_en agregada a products';
    END IF;
END $$;

-- PASO 5: Verificar que filename en images sea NOT NULL
DO $$
BEGIN
    -- Rellenar filename NULL con valor derivado de cloudinary_public_id
    UPDATE images
    SET filename = COALESCE(
        regexp_replace(cloudinary_public_id, '^.*/', ''),
        'image_' || id || '.jpg'
    )
    WHERE filename IS NULL;

    -- Asegurar constraint NOT NULL
    ALTER TABLE images ALTER COLUMN filename SET NOT NULL;
    RAISE NOTICE 'Columna filename en images verificada (NOT NULL)';
END $$;

-- PASO 6: Agregar client_id a images si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'images' AND column_name = 'client_id'
    ) THEN
        ALTER TABLE images ADD COLUMN client_id VARCHAR(36);

        -- Rellenar client_id desde product.client_id
        UPDATE images i
        SET client_id = p.client_id
        FROM products p
        WHERE i.product_id = p.id AND i.client_id IS NULL;

        -- Agregar FK constraint
        ALTER TABLE images
        ADD CONSTRAINT images_client_id_fkey
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE;

        RAISE NOTICE 'Columna client_id agregada a images con FK';
    END IF;
END $$;

-- VERIFICACIÓN FINAL
DO $$
DECLARE
    cat_count INT;
    prod_count INT;
    img_count INT;
BEGIN
    SELECT COUNT(*) INTO cat_count FROM categories;
    SELECT COUNT(*) INTO prod_count FROM products;
    SELECT COUNT(*) INTO img_count FROM images;

    RAISE NOTICE '=== VERIFICACIÓN POST-MIGRACIÓN ===';
    RAISE NOTICE 'Categorías: %', cat_count;
    RAISE NOTICE 'Productos: %', prod_count;
    RAISE NOTICE 'Imágenes: %', img_count;

    -- Verificar integridad
    IF cat_count = 0 OR prod_count = 0 THEN
        RAISE EXCEPTION 'ERROR: Datos perdidos durante migración';
    END IF;
END $$;

COMMIT;

-- ================================================================
-- FIN DE MIGRACIÓN
-- ================================================================
