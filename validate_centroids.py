"""
Script para validar y recalcular centroides de categorías.
Asegura que todas las categorías con productos tengan centroides válidos.
"""
import sys
import os

# Add backend directory to path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clip_admin_backend')
sys.path.insert(0, backend_path)

# Change to backend directory
os.chdir(backend_path)

# Now import - app.py's create_app should be accessible
import app as flask_app
from app import db
from app.models.client import Client
from app.models.category import Category
from app.models.product import Product

def validate_and_fix_centroids():
    """Valida y recalcula centroides faltantes"""
    app = flask_app.create_app()

    with app.app_context():
        print("🔍 Validando centroides de categorías...")
        print("=" * 80)

        # Obtener todos los clientes activos
        clients = Client.query.filter_by(is_active=True).all()

        total_categories = 0
        missing_centroids = 0
        fixed_centroids = 0

        for client in clients:
            print(f"\n📦 Cliente: {client.name}")

            # Obtener categorías con productos activos
            categories = db.session.query(Category).join(
                Product, Product.category_id == Category.id
            ).filter(
                Product.client_id == client.id,
                Product.is_active == True,
                Category.is_active == True
            ).distinct().all()

            print(f"   Categorías con productos: {len(categories)}")

            for cat in categories:
                total_categories += 1

                # Contar productos con imágenes procesadas
                products_with_images = db.session.query(Product).join(
                    Product.images
                ).filter(
                    Product.category_id == cat.id,
                    Product.is_active == True
                ).distinct().count()

                has_centroid = cat.centroid_embedding is not None

                status = "✅" if has_centroid else "❌"
                print(f"   {status} {cat.name:<40s} | Productos: {products_with_images:<3d} | Centroide: {has_centroid}")

                if not has_centroid and products_with_images > 0:
                    missing_centroids += 1
                    print(f"      🔧 Recalculando centroide...")

                    try:
                        success = cat.update_centroid_embedding(force_recalculate=True)
                        if success:
                            db.session.commit()
                            fixed_centroids += 1
                            print(f"      ✅ Centroide recalculado ({cat.centroid_image_count} imágenes)")
                        else:
                            print(f"      ⚠️ No se pudo calcular centroide (sin embeddings válidos)")
                    except Exception as e:
                        print(f"      ❌ Error: {e}")
                        db.session.rollback()

        print("\n" + "=" * 80)
        print("📊 RESUMEN:")
        print(f"   Total categorías evaluadas: {total_categories}")
        print(f"   Centroides faltantes: {missing_centroids}")
        print(f"   Centroides recalculados: {fixed_centroids}")

        if missing_centroids == 0:
            print("\n✅ ¡Todos los centroides están OK!")
        elif fixed_centroids == missing_centroids:
            print("\n✅ ¡Todos los centroides faltantes fueron recalculados!")
        else:
            print(f"\n⚠️ Quedan {missing_centroids - fixed_centroids} centroides sin poder calcular")
            print("   (Probablemente categorías sin productos con imágenes procesadas)")

if __name__ == '__main__':
    validate_and_fix_centroids()
