"""
Script para diagnosticar por qué la detección de categorías falla
Simula una búsqueda y muestra las similitudes calculadas
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json
import numpy as np

# Cargar .env.local
ROOT = Path(__file__).resolve().parents[2]
ENV_LOCAL = ROOT / '.env.local'
if ENV_LOCAL.exists():
    load_dotenv(ENV_LOCAL)
else:
    load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print('❌ DATABASE_URL no definido')
    sys.exit(1)

engine = create_engine(DATABASE_URL, future=True)

print("=" * 70)
print("🔍 DIAGNÓSTICO DE DETECCIÓN DE CATEGORÍAS")
print("=" * 70)

with engine.connect() as conn:
    # 1. Ver qué categorías tienen centroides
    result = conn.execute(text("""
        SELECT
            id,
            name,
            name_en,
            parent_id,
            is_leaf,
            centroid_image_count,
            confidence_threshold,
            LENGTH(centroid_embedding) as centroid_len
        FROM categories
        WHERE centroid_embedding IS NOT NULL
        ORDER BY centroid_image_count DESC
    """))

    print("\n📊 CATEGORÍAS CON CENTROIDES:")
    categories = []
    for row in result:
        cat = {
            'id': row[0],
            'name': row[1],
            'name_en': row[2],
            'parent_id': row[3],
            'is_leaf': row[4],
            'image_count': row[5],
            'threshold': row[6],
            'centroid_len': row[7]
        }
        categories.append(cat)
        parent = f" (parent: {str(row[3])[:8]})" if row[3] else " (ROOT)"
        leaf = "🍃" if row[4] else "🌳"
        print(f"  {leaf} {row[1]:30} | {row[5]:3} imgs | threshold: {row[6]:.2f} | centroid: {row[7]:6} bytes{parent}")

    # 2. Tomar una imagen de ejemplo de cada categoría principal
    print("\n🖼️  EMBEDDINGS DE MUESTRA POR CATEGORÍA:")

    sample_categories = ['Medio Delantal', 'Delantal Completo', 'CAMISA MANGA HOMBRES', 'AMBO VESTE HOMBRES']

    for cat_name in sample_categories:
        result = conn.execute(text("""
            SELECT i.id, i.filename, p.name as product_name, c.name as category
            FROM images i
            JOIN products p ON i.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE c.name = :cat_name
              AND i.clip_embedding IS NOT NULL
            LIMIT 1
        """), {'cat_name': cat_name})

        row = result.fetchone()
        if row:
            print(f"\n  📦 {cat_name}:")
            print(f"     Producto: {row[2]}")
            print(f"     Archivo: {row[1][:50]}")

    # 3. Verificar distribución de similitudes entre categorías hermanas
    print("\n🔗 ANÁLISIS DE SEPARACIÓN ENTRE CATEGORÍAS:")

    # Obtener centroides de delantales (deberían estar bien separados)
    result = conn.execute(text("""
        SELECT name, centroid_embedding
        FROM categories
        WHERE name IN ('Medio Delantal', 'Delantal Completo')
          AND centroid_embedding IS NOT NULL
    """))

    centroids = {}
    for row in result:
        centroids[row[0]] = np.array(json.loads(row[1]))

    if len(centroids) == 2:
        medio = centroids['Medio Delantal']
        completo = centroids['Delantal Completo']

        # Normalizar
        medio_norm = medio / np.linalg.norm(medio)
        completo_norm = completo / np.linalg.norm(completo)

        # Similitud entre hermanos
        similarity = float(np.dot(medio_norm, completo_norm))
        print(f"\n  Similitud Medio Delantal ↔ Delantal Completo: {similarity:.4f}")
        print(f"  → {'✓ Bien separados' if similarity < 0.85 else '⚠️ Demasiado similares'}")

    # 4. Ver si hay categorías con muy pocos embeddings
    print("\n⚠️  CATEGORÍAS CON POCOS DATOS (<5 imágenes):")
    low_count_cats = [c for c in categories if c['image_count'] < 5]
    if low_count_cats:
        for cat in low_count_cats:
            print(f"  • {cat['name']:30} | {cat['image_count']} imágenes")
    else:
        print("  ✓ Todas las categorías tienen >= 5 imágenes")

    # 5. Ver distribución de thresholds
    print("\n🎯 DISTRIBUCIÓN DE THRESHOLDS DE CONFIANZA:")
    thresholds = [c['threshold'] for c in categories]
    if thresholds:
        print(f"  • Mínimo: {min(thresholds):.2f}")
        print(f"  • Máximo: {max(thresholds):.2f}")
        print(f"  • Promedio: {sum(thresholds)/len(thresholds):.2f}")

print("\n" + "=" * 70)
