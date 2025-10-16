#!/usr/bin/env python3
"""
Script para sincronizar la estructura de la tabla images en PostgreSQL
con el modelo SQLAlchemy actual
"""
import asyncio
import asyncpg

# URL de base de datos PostgreSQL en Railway
POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def sync_images_table():
    """Sincroniza la estructura de la tabla images"""

    print("🔧 SINCRONIZANDO ESTRUCTURA DE TABLA IMAGES")
    print("=" * 50)

    # Conectar a PostgreSQL
    conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 1. Verificar campos existentes
        print("📋 Verificando estructura actual...")
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'images'
            ORDER BY ordinal_position
        """)

        print("Campos actuales:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")

        # 2. Agregar campos faltantes si no existen
        fields_to_add = [
            ("base64_data", "TEXT"),
            ("mime_type", "VARCHAR(100)"),
            ("alt_text", "VARCHAR(255)"),
            ("display_order", "INTEGER DEFAULT 0"),
            ("is_processed", "BOOLEAN DEFAULT false"),
            ("clip_embedding", "TEXT"),
            ("upload_status", "VARCHAR(50) DEFAULT 'pending'"),
            ("error_message", "TEXT"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]

        existing_columns = [col['column_name'] for col in columns]

        print(f"\n🔨 Agregando campos faltantes...")
        for field_name, field_type in fields_to_add:
            if field_name not in existing_columns:
                try:
                    await conn.execute(f"ALTER TABLE images ADD COLUMN {field_name} {field_type}")
                    print(f"  ✅ Agregado: {field_name} {field_type}")
                except Exception as e:
                    print(f"  ❌ Error agregando {field_name}: {e}")
            else:
                print(f"  ⏭️  Ya existe: {field_name}")

        # 3. Renombrar campo si existe
        if 'original_filename' in existing_columns and 'original_url' not in existing_columns:
            try:
                await conn.execute("ALTER TABLE images RENAME COLUMN original_filename TO original_url")
                print(f"  ✅ Renombrado: original_filename -> original_url")
            except Exception as e:
                print(f"  ❌ Error renombrando: {e}")

        # 4. Cambiar tipos de campos si es necesario
        try:
            await conn.execute("ALTER TABLE images ALTER COLUMN original_url TYPE VARCHAR(500)")
            print(f"  ✅ Actualizado tipo: original_url a VARCHAR(500)")
        except Exception as e:
            print(f"  ⚠️  Tipo original_url ya correcto o error: {e}")

        # 5. Verificar estructura final
        print(f"\n🔍 ESTRUCTURA FINAL:")
        final_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'images'
            ORDER BY ordinal_position
        """)

        for col in final_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  ✅ {col['column_name']}: {col['data_type']} {nullable}")

        # 6. Contar registros
        count = await conn.fetchval("SELECT COUNT(*) FROM images")
        print(f"\n📊 Total de imágenes: {count}")

        print(f"\n✨ ¡ESTRUCTURA SINCRONIZADA!")
        return True

    except Exception as e:
        print(f"❌ Error durante la sincronización: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(sync_images_table())
    if success:
        print("\n🎯 TABLA IMAGES LISTA PARA EL MODELO SQLALCHEMY")
    else:
        print("\n💥 Error en la sincronización")
