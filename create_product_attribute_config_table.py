"""
Crea la tabla product_attribute_config en Railway si no existe.
Compatible con el modelo ProductAttributeConfig.
"""
import psycopg2

DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

DDL = """
CREATE TABLE IF NOT EXISTS product_attribute_config (
    id SERIAL PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    key VARCHAR(100) NOT NULL,
    label VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL,
    required BOOLEAN DEFAULT FALSE,
    options JSONB,
    field_order INTEGER DEFAULT 0,
    expose_in_search BOOLEAN DEFAULT FALSE
);

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_attr_config_client ON product_attribute_config(client_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attr_config_client_key ON product_attribute_config(client_id, key);
"""

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(DDL)
            print("✅ Tabla product_attribute_config verificada/creada en Railway")
    except Exception as e:
        print(f"❌ Error creando tabla: {e}")
        raise
    finally:
        conn.close()
        print("🔌 Conexión cerrada")

if __name__ == "__main__":
    main()
