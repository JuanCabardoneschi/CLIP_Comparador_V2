-- SQL idempotente para re-agregar vision_hint a categories
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS vision_hint TEXT;

-- Opcional: comentario de ayuda
COMMENT ON COLUMN categories.vision_hint IS 'Aclaraciones para GPT-4 Vision: desambiguaciones visuales por categoría';
