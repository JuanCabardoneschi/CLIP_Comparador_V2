"""
Script para verificar si las imágenes tienen base64_data en la BD
Soporta tanto BD local como Railway (producción)
"""
import sys
import os
from pathlib import Path

# Agregar raíz del proyecto al path para imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def check_base64_status(env='local'):
    """
    Verifica el estado de base64_data en las imágenes

    Args:
        env: 'local' para BD local, 'railway' para producción
    """
    if env == 'local':
        # Cargar variables de entorno locales
        env_file = project_root / '.env.local'
        load_dotenv(env_file)
        DATABASE_URL = os.getenv("DATABASE_URL")
        env_name = "LOCAL"
    else:
        # Conectar a Railway
        DATABASE_URL = "postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway"
        env_name = "RAILWAY (PRODUCCIÓN)"

    if not DATABASE_URL:
        print(f"❌ Error: DATABASE_URL no encontrada")
        return False

    print(f"🔗 Conectando a BD {env_name}...")
    print(f"   {DATABASE_URL[:60]}...")

    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Contar imágenes totales
            result = conn.execute(text("SELECT COUNT(*) as total FROM images"))
            total = result.fetchone()[0]

            # Contar imágenes con base64_data
            result = conn.execute(text("SELECT COUNT(*) as con_base64 FROM images WHERE base64_data IS NOT NULL AND base64_data != ''"))
            con_base64 = result.fetchone()[0]

            # Contar imágenes procesadas
            result = conn.execute(text("SELECT COUNT(*) as procesadas FROM images WHERE is_processed = true"))
            procesadas = result.fetchone()[0]

            sin_base64 = total - con_base64

            print(f"\n📊 ESTADO DE IMÁGENES EN {env_name}:")
            print(f"   Total imágenes: {total}")
            print(f"   Imágenes procesadas: {procesadas} ({procesadas*100/total if total > 0 else 0:.1f}%)")
            print(f"\n📸 ESTADO DE BASE64:")
            print(f"   Con base64_data: {con_base64} ({con_base64*100/total if total > 0 else 0:.1f}%)")
            print(f"   Sin base64_data: {sin_base64} ({sin_base64*100/total if total > 0 else 0:.1f}%)")

            if sin_base64 > 0:
                print(f"\n⚠️  Hay {sin_base64} imágenes sin base64_data")
                print(f"   Esto puede afectar el rendimiento del widget")

                # Mostrar algunas imágenes sin base64
                result = conn.execute(text("""
                    SELECT i.id, i.original_filename, p.name as product_name
                    FROM images i
                    LEFT JOIN products p ON i.product_id = p.id
                    WHERE i.base64_data IS NULL OR i.base64_data = ''
                    LIMIT 5
                """))

                print(f"\n   Ejemplos de imágenes sin base64:")
                for row in result:
                    print(f"   - ID: {row[0]}, Archivo: {row[1]}, Producto: {row[2]}")
            else:
                print(f"\n✅ Todas las imágenes tienen base64_data!")

            return sin_base64 == 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Verificar estado de base64 en imágenes')
    parser.add_argument('--env', choices=['local', 'railway'], default='local',
                        help='Entorno a verificar (default: local)')

    args = parser.parse_args()

    success = check_base64_status(args.env)
    sys.exit(0 if success else 1)
