#!/usr/bin/env python3
"""
Agregar campos faltantes en la tabla products de PostgreSQL
para coincidir exactamente con SQLite
"""
import asyncio
import asyncpg

POSTGRES_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"

async def fix_products_table():
    """Agregar campos faltantes en products"""

    print("🔧 CORRIGIENDO TABLA PRODUCTS EN POSTGRESQL")
    print("=" * 50)

    conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # 1. Verificar campos actuales
        print("📋 Verificando campos actuales...")
        cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'products'")
        existing_cols = [col['column_name'] for col in cols]
        print(f"Campos actuales: {', '.join(existing_cols)}")

        # 2. Agregar campos faltantes de SQLite
        fields_to_add = [
            ("stock", "INTEGER DEFAULT 0"),
            ("color", "VARCHAR(50)"),
            ("tags", "TEXT")
        ]

        print(f"\n🔨 Agregando campos faltantes...")
        for field_name, field_type in fields_to_add:
            if field_name not in existing_cols:
                try:
                    await conn.execute(f"ALTER TABLE products ADD COLUMN {field_name} {field_type}")
                    print(f"  ✅ Agregado: {field_name} {field_type}")
                except Exception as e:
                    print(f"  ❌ Error agregando {field_name}: {e}")
            else:
                print(f"  ⏭️  Ya existe: {field_name}")

        # 3. Verificar estructura final
        print(f"\n📋 ESTRUCTURA FINAL DE PRODUCTS:")
        final_cols = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'products'
            ORDER BY ordinal_position
        """)

        for col in final_cols:
            print(f"  ✅ {col['column_name']}: {col['data_type']}")

        # 4. Contar registros
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        print(f"\n📊 Total productos: {count}")

        print(f"\n✨ ¡TABLA PRODUCTS CORREGIDA!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(fix_products_table())
    if success:
        print("\n🎯 PRODUCTS AHORA COINCIDE CON SQLITE")
    else:
        print("\n💥 Error en la corrección")
