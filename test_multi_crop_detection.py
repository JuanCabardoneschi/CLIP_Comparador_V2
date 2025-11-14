"""
Test Multi-Crop Detection Strategy
Prueba si multi-escala mejora detección de categorías sin object detection.

USO: python test_multi_crop_detection.py
"""
import sys
import os
from pathlib import Path

# Cambiar al directorio clip_admin_backend para imports correctos
backend_dir = Path(__file__).parent / "clip_admin_backend"
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

import numpy as np
from PIL import Image
import logging

# Ahora importar desde app
from app import db
from app.models.category import Category
from app.models.client import Client
from app.models.product import Product
from app.blueprints.embeddings import (
    detect_categories_multi_crop,
    get_clip_model,
    generate_simple_embedding
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_categories_single_scale(image_path: str, client_id: str, threshold: float = 0.3):
    """Detección tradicional con embedding global."""
    model, processor = get_clip_model()

    # Encode imagen
    img_embedding = generate_simple_embedding(image_path, model, processor)
    # Normalizar
    img_embedding = np.array(img_embedding)
    img_embedding = img_embedding / np.linalg.norm(img_embedding)

    # Obtener categorías activas del cliente
    categories = db.session.query(Category).join(
        Product, Product.category_id == Category.id
    ).filter(
        Product.client_id == client_id,
        1 == 1  # categorías planas; condición neutralizada
    ).distinct().all()

    # Encode prompts
    results = []
    for cat in categories:
        if not cat.clip_prompt:
            continue

        prompt_embedding = generate_simple_embedding(cat.clip_prompt, model, processor)
        prompt_embedding = np.array(prompt_embedding)
        prompt_embedding = prompt_embedding / np.linalg.norm(prompt_embedding)

        score = np.dot(img_embedding, prompt_embedding)

        results.append({
            'category_id': cat.id,
            'category_name': cat.name,
            'score': float(score),
            'passes': score >= threshold
        })

    return sorted(results, key=lambda x: x['score'], reverse=True)


def detect_categories_multi_scale(image_path: str, client_id: str, threshold: float = 0.3):
    """Detección multi-escala con aggregate scoring (wrapper de detect_categories_multi_crop)."""
    return detect_categories_multi_crop(
        image_path,
        client_id,
        threshold=threshold,
        top_k=20  # Traer todos para comparar
    )


def compare_methods(image_path: str, client_id: str):
    """Compara single-scale vs multi-scale."""
    print(f"\n{'='*80}")
    print(f"COMPARANDO MÉTODOS: {Path(image_path).name}")
    print(f"{'='*80}\n")

    # Single-scale
    print("🔍 SINGLE-SCALE (embedding global):")
    single_results = detect_categories_single_scale(image_path, client_id)
    for r in single_results[:5]:
        status = "✅" if r['passes'] else "❌"
        print(f"  {status} {r['category_name']:30s} score={r['score']:.3f}")

    # Multi-scale
    print("\n🔍 MULTI-SCALE (6 crops + max aggregation):")
    multi_results = detect_categories_multi_scale(image_path, client_id)
    for r in multi_results[:5]:
        status = "✅" if r['passes'] else "❌"
        print(f"  {status} {r['category_name']:30s} score={r['score']:.3f} (best_crop={r['best_crop']})")

    # Análisis de mejora
    print("\n📊 ANÁLISIS DE MEJORA:")
    for single, multi in zip(single_results, multi_results):
        if single['category_id'] == multi['category_id']:
            delta = multi['score'] - single['score']
            if abs(delta) > 0.05:
                emoji = "📈" if delta > 0 else "📉"
                print(f"  {emoji} {single['category_name']:30s} delta={delta:+.3f}")

    return single_results, multi_results


def main():
    """Test con imágenes de productos existentes."""
    # Crear app de Flask
    from app.py import create_app
    flask_app = create_app()

    with flask_app.app_context():
        # Buscar cliente Goody Store (tiene delantales)
        client = Client.query.filter_by(name="Goody Store").first()
        if not client:
            print("❌ Cliente 'Goody Store' no encontrado")
            return

        print(f"✅ Cliente: {client.name} (ID: {client.id})")
        print(f"   Threshold: {client.category_confidence_threshold}%")

        # Buscar productos con imágenes
        products = Product.query.filter_by(
            client_id=client.id,
            is_active=True
        ).limit(3).all()

        if not products:
            print("❌ No hay productos con imágenes")
            return

        # Test con cada producto
        for product in products:
            if not product.images:
                continue

            image = product.images[0]
            # Usar display_url del modelo Image
            image_url = image.display_url

            print(f"\n\n{'='*80}")
            print(f"PRODUCTO: {product.name}")
            print(f"Categoría real: {product.category.name if product.category else 'N/A'}")
            print(f"Imagen: {image_url}")
            print(f"{'='*80}")

            # Nota: Para test local necesitamos descargar la imagen de Cloudinary
            # Por ahora solo mostramos la comparación de algoritmos
            print("\n⚠️ Para ejecutar el test completo, descarga imágenes de Cloudinary")
            print("   Comando: python download_cloudinary_images.py")


if __name__ == "__main__":
    main()
