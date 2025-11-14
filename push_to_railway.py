"""
Subir datos locales faltantes a Railway
Sincroniza vision_hints y otros datos que solo existen en local
"""
import psycopg2
from clip_admin_backend.app import create_app, db
from clip_admin_backend.app.models.category import Category

RAILWAY_CONFIG = {
    'host': 'ballast.proxy.rlwy.net',
    'port': 54363,
    'database': 'railway',
    'user': 'postgres',
    'password': 'btjTLhgRVQGljdqRBJoJpHjQikqbxcTp'
}

def push_missing_data():
    """Subir datos locales que no existen en Railway"""
    print("🚀 Iniciando sincronización Local → Railway")
    app = create_app()

    with app.app_context():
        railway_conn = psycopg2.connect(**RAILWAY_CONFIG)
        railway_cur = railway_conn.cursor()

        try:
            # 1. Categorías con vision_hint
            print("\n📁 Actualizando vision_hints en categorías...")
            local_cats = Category.query.all()
            updated_count = 0

            for cat in local_cats:
                if cat.vision_hint:
                    railway_cur.execute(
                        "UPDATE categories SET vision_hint = %s WHERE id = %s",
                        (cat.vision_hint, cat.id)
                    )
                    print(f"  ✅ {cat.name}: '{cat.vision_hint[:50]}...'")
                    updated_count += 1

            railway_conn.commit()
            print(f"\n✅ {updated_count} vision hints sincronizados")

            # 2. Verificar sincronización
            print("\n🔍 Verificando sincronización...")
            railway_cur.execute("SELECT COUNT(*) FROM categories WHERE vision_hint IS NOT NULL")
            count_with_hint = railway_cur.fetchone()[0]
            print(f"  ℹ️ Categorías con vision_hint en Railway: {count_with_hint}")

        except Exception as e:
            railway_conn.rollback()
            print(f"❌ Error durante sincronización: {e}")
            raise
        finally:
            railway_cur.close()
            railway_conn.close()

    print("\n✅ Sincronización completada")

if __name__ == '__main__':
    import sys
    if '--dry-run' in sys.argv:
        print("🛟 Modo DRY-RUN: Solo mostrando qué se sincronizaría")
        print("   Ejecuta sin --dry-run para aplicar cambios")
    else:
        if input("¿Continuar con la sincronización? (y/n): ").lower() == 'y':
            push_missing_data()
        else:
            print("❌ Cancelado por usuario")
