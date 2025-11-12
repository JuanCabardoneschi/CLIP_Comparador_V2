"""
Debug: Analizar detección de múltiples categorías con datos REALES de demo_store
Objetivo: Entender por qué NO detecta las categorías correctas
"""

import sys
import os

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
backend_dir = os.path.join(parent_dir, 'clip_admin_backend')

sys.path.insert(0, backend_dir)
sys.path.insert(0, parent_dir)

# Import Flask app
from clip_admin_backend.app import app as flask_app
from app.models import Client, Category, Product, Image
from app import db
from sqlalchemy import func, text
import json

def analyze_demo_store_detection():
    """Analizar estado actual del sistema de detección para demo_store"""

    with flask_app.app_context():
        # 1. Obtener cliente demo_store
        demo_client = Client.query.filter_by(name='demo_store').first()
        if not demo_client:
            print("❌ No existe cliente demo_store")
            return

        print(f"✅ Cliente: {demo_client.name} (ID: {demo_client.id})")
        print("=" * 80)

        # 2. Obtener TODAS las categorías con centroides de demo_store
        categories_with_centroids = Category.query.filter(
            Category.client_id == demo_client.id,
            Category.centroid_embedding.isnot(None)
        ).all()

        print(f"\n📊 CATEGORÍAS CON CENTROIDES (demo_store): {len(categories_with_centroids)}")
        print("=" * 80)

        category_stats = []
        for cat in categories_with_centroids:
            # Contar productos con imágenes que tienen embeddings
            products_count = db.session.query(func.count(func.distinct(Product.id))).join(
                Image, Product.id == Image.product_id
            ).filter(
                Product.category_id == cat.id,
                Product.client_id == demo_client.id,
                Image.embedding.isnot(None)
            ).scalar()

            # Contar imágenes totales con embedding
            images_count = Image.query.join(Product).filter(
                Product.category_id == cat.id,
                Product.client_id == demo_client.id,
                Image.embedding.isnot(None)
            ).count()

            category_stats.append({
                'id': str(cat.id),
                'name': cat.name,
                'parent': cat.parent.name if cat.parent else 'ROOT',
                'products': products_count,
                'images': images_count,
                'threshold': cat.similarity_threshold,
                'centroid_updated': cat.centroid_last_updated.strftime('%d/%m %H:%M') if cat.centroid_last_updated else 'Never'
            })

        # Ordenar por número de imágenes (descendente)
        category_stats.sort(key=lambda x: x['images'], reverse=True)

        for stat in category_stats:
            emoji = "🍃" if stat['parent'] != 'ROOT' else "🌳"
            print(f"{emoji} {stat['name']:<30} | Padre: {stat['parent']:<20} | "
                  f"Prod: {stat['products']:>2} | Imgs: {stat['images']:>2} | "
                  f"Threshold: {stat['threshold']:.2f} | Update: {stat['centroid_updated']}")

        # 3. Analizar estructura jerárquica
        print(f"\n\n🌲 ESTRUCTURA JERÁRQUICA")
        print("=" * 80)

        root_categories = [c for c in categories_with_centroids if c.parent_id is None]
        print(f"Categorías raíz: {len(root_categories)}")

        for root in root_categories:
            children = [c for c in categories_with_centroids if c.parent_id == root.id]
            print(f"\n🌳 {root.name} (threshold: {root.similarity_threshold:.2f})")
            if children:
                for child in children:
                    imgs = next(s['images'] for s in category_stats if s['id'] == str(child.id))
                    print(f"   └─ 🍃 {child.name} ({imgs} imgs, threshold: {child.similarity_threshold:.2f})")

        # 4. Identificar categorías con POCOS datos
        print(f"\n\n⚠️ CATEGORÍAS CON POCOS DATOS (<5 imágenes)")
        print("=" * 80)

        weak_categories = [s for s in category_stats if s['images'] < 5]
        for stat in weak_categories:
            print(f"  ❗ {stat['name']:<30} | {stat['images']} imgs | Parent: {stat['parent']}")

        if not weak_categories:
            print("  ✅ Todas las categorías tienen ≥5 imágenes")

        # 5. Analizar EJEMPLOS de productos por categoría (top 5)
        print(f"\n\n🔍 EJEMPLOS DE PRODUCTOS (Top 5 categorías por cantidad de imágenes)")
        print("=" * 80)

        for stat in category_stats[:5]:
            cat = Category.query.get(stat['id'])
            products = Product.query.join(Image).filter(
                Product.category_id == cat.id,
                Product.client_id == demo_client.id,
                Image.embedding.isnot(None)
            ).distinct().limit(3).all()

            print(f"\n📦 {stat['name']} ({stat['images']} imágenes)")
            for prod in products:
                images_count = Image.query.filter(
                    Image.product_id == prod.id,
                    Image.embedding.isnot(None)
                ).count()
                print(f"   • {prod.name[:50]} ({images_count} imgs)")

        # 6. Verificar distribución de thresholds
        print(f"\n\n🎯 DISTRIBUCIÓN DE THRESHOLDS")
        print("=" * 80)

        thresholds = [s['threshold'] for s in category_stats]
        print(f"  Min: {min(thresholds):.2f}")
        print(f"  Max: {max(thresholds):.2f}")
        print(f"  Avg: {sum(thresholds)/len(thresholds):.2f}")
        print(f"  Varianza: {max(thresholds) - min(thresholds):.2f}")

        # Contar categorías por rango de threshold
        ranges = {
            '0.60-0.70': len([t for t in thresholds if 0.60 <= t < 0.70]),
            '0.70-0.75': len([t for t in thresholds if 0.70 <= t < 0.75]),
            '0.75-0.80': len([t for t in thresholds if 0.75 <= t < 0.80]),
            '0.80+': len([t for t in thresholds if t >= 0.80])
        }
        print("\n  Por rango:")
        for range_name, count in ranges.items():
            print(f"    {range_name}: {count} categorías")

        # 7. PREGUNTA CLAVE: ¿Qué categorías esperamos detectar en las pruebas?
        print(f"\n\n❓ CATEGORÍAS ESPERADAS EN PRUEBAS DEL USUARIO")
        print("=" * 80)
        print("  Prueba 1: Blazer rosa mujer")
        blazers = [s for s in category_stats if 'blazer' in s['name'].lower() or 'saco' in s['name'].lower()]
        if blazers:
            for b in blazers:
                print(f"    ✓ {b['name']} ({b['images']} imgs, threshold: {b['threshold']:.2f})")
        else:
            print(f"    ❌ NO HAY categorías de blazer/saco en demo_store")

        print("\n  Prueba 2: Musculosa negra")
        musculosas = [s for s in category_stats if 'musculosa' in s['name'].lower() or 'tank' in s['name'].lower() or 'remera' in s['name'].lower()]
        if musculosas:
            for m in musculosas:
                print(f"    ✓ {m['name']} ({m['images']} imgs, threshold: {m['threshold']:.2f})")
        else:
            print(f"    ❌ NO HAY categorías de musculosa en demo_store")

        print("\n  Prueba 3: Vestido negro")
        vestidos = [s for s in category_stats if 'vestido' in s['name'].lower() or 'dress' in s['name'].lower()]
        if vestidos:
            for v in vestidos:
                print(f"    ✓ {v['name']} ({v['images']} imgs, threshold: {v['threshold']:.2f})")
        else:
            print(f"    ❌ NO HAY categorías de vestido en demo_store")

        print("\n  Prueba 4: Delantal café")
        delantales = [s for s in category_stats if 'delantal' in s['name'].lower() or 'apron' in s['name'].lower()]
        if delantales:
            for d in delantales:
                print(f"    ✓ {d['name']} ({d['images']} imgs, threshold: {d['threshold']:.2f})")
        else:
            print(f"    ❌ NO HAY categorías de delantal en demo_store")

if __name__ == '__main__':
    analyze_demo_store_detection()
