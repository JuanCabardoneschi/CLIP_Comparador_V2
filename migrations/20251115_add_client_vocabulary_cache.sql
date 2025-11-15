-- Crear tabla de caché de vocabulario por cliente
-- Entorno: PostgreSQL (requerido)

CREATE TABLE IF NOT EXISTS client_vocabulary_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vocabulary JSONB NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (client_id)
);

-- Índices recomendados
CREATE INDEX IF NOT EXISTS idx_vocab_cache_client ON client_vocabulary_cache(client_id);
CREATE INDEX IF NOT EXISTS idx_vocab_cache_updated_at ON client_vocabulary_cache(updated_at);

-- Trigger opcional para updated_at (no obligatorio para esta fase)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'set_updated_at_vocabulary_cache'
    ) THEN
        CREATE OR REPLACE FUNCTION set_updated_at_vocabulary_cache()
        RETURNS TRIGGER AS $func$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_set_updated_at_vocabulary_cache'
    ) THEN
        CREATE TRIGGER trg_set_updated_at_vocabulary_cache
        BEFORE UPDATE ON client_vocabulary_cache
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_at_vocabulary_cache();
    END IF;
END$$;
