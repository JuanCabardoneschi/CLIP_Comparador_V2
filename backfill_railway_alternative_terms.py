#!/usr/bin/env python3
"""
Backfill de alternative_terms para categorías en Railway (Test Clip - TiendaNube).
Genera términos alternativos usando MiniLM con filtrado por grupos.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import importlib.util

# Importar el servicio directamente sin inicializar Flask
service_path = os.path.join(
    os.path.dirname(__file__),
    'clip_admin_backend',
    'app',
    'services',
    'alternative_terms_generator.py'
)

spec = importlib.util.spec_from_file_location("alt_terms_gen", service_path)
alt_terms_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alt_terms_module)

generate_alternative_terms = alt_terms_module.generate_alternative_terms

# Railway Database Connection (credenciales actualizadas)
RAILWAY_DB_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum'
}

def get_railway_connection():
    """Conectar a Railway PostgreSQL"""
    return psycopg2.connect(**RAILWAY_DB_CONFIG)

def main():
    print("="*80)
    print("🚂 BACKFILL: Alternative Terms en Railway (Test Clip - TiendaNube)")
    print("="*80)

    conn = get_railway_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Buscar categorías de Test Clip con alternative_terms NULL o vacío
        query = """
            SELECT cat.id, cat.name, cat.alternative_terms, c.name as client_name
            FROM categories cat
            JOIN clients c ON c.id = cat.client_id
            WHERE c.integration_type = 'tiendanube'
            AND (cat.alternative_terms IS NULL OR cat.alternative_terms = '')
            ORDER BY cat.name
        """

        cursor.execute(query)
        categories = cursor.fetchall()

        if not categories:
            print("\n✅ No hay categorías sin alternative_terms en Railway")
            return

        print(f"\n✅ Encontradas {len(categories)} categorías sin alternative_terms:")
        for cat in categories:
            print(f"   - {cat['name']} (Cliente: {cat['client_name']})")

        # Confirmar antes de proceder
        print(f"\n{'='*80}")
        response = input("¿Generar alternative_terms para estas categorías? (s/N): ").strip().lower()
        if response != 's':
            print("\n⚠️ Operación cancelada")
            return

        print(f"\n{'='*80}")
        print("🔄 GENERANDO ALTERNATIVE_TERMS...")
        print(f"{'='*80}\n")

        success_count = 0
        empty_count = 0
        error_count = 0

        for cat in categories:
            category_id = cat['id']
            category_name = cat['name']

            try:
                # Generar alternative_terms
                alternative_terms = generate_alternative_terms(category_name)

                if alternative_terms:
                    # Actualizar en Railway
                    update_query = """
                        UPDATE categories
                        SET alternative_terms = %s, updated_at = NOW()
                        WHERE id = %s
                    """
                    cursor.execute(update_query, (alternative_terms, category_id))
                    conn.commit()

                    print(f"✅ {category_name}")
                    print(f"   → {alternative_terms}\n")
                    success_count += 1
                else:
                    print(f"⚠️ {category_name}")
                    print(f"   → (vacío - no se encontraron términos con threshold 0.50)\n")
                    empty_count += 1

            except Exception as e:
                print(f"❌ {category_name}")
                print(f"   Error: {e}\n")
                error_count += 1
                conn.rollback()

        # Resumen final
        print(f"\n{'='*80}")
        print("📊 RESUMEN")
        print(f"{'='*80}")
        print(f"✅ Éxitos: {success_count}")
        print(f"⚠️ Vacíos: {empty_count}")
        print(f"❌ Errores: {error_count}")
        print(f"{'='*80}\n")

        # Verificar resultados
        print("🔍 VERIFICANDO RESULTADOS EN RAILWAY...")
        cursor.execute("""
            SELECT cat.name, cat.alternative_terms
            FROM categories cat
            JOIN clients c ON c.id = cat.client_id
            WHERE c.integration_type = 'tiendanube'
            ORDER BY cat.name
        """)

        results = cursor.fetchall()
        print("\n📋 Estado final de categorías:")
        for row in results:
            status = "✅" if row['alternative_terms'] else "⚠️"
            terms = row['alternative_terms'] or "(vacío)"
            print(f"{status} {row['name']}: {terms}")

        print(f"\n{'='*80}")
        print("✅ Backfill completado exitosamente")
        print(f"{'='*80}")

    except Exception as e:
        print(f"\n❌ Error durante backfill: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Operación interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
