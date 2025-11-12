"""
Test Multi-Crop Detection - Version Simplificada
Ejecutar desde clip_admin_backend/: python ../test_multi_crop_simple.py
"""
from app import db
from app.models.client import Client
from app.blueprints.embeddings import detect_categories_multi_crop, get_clip_model
import logging

logging.basicConfig(level=logging.INFO)

# Test
client = Client.query.filter_by(name="Goody Store").first()
if not client:
    print("❌ Cliente 'Goody Store' no encontrado")
    exit(1)

print(f"✅ Cliente: {client.name} (ID: {client.id})")
print(f"   Threshold: {client.category_confidence_threshold}%")

# URL de imagen de prueba (reemplazar con URL real de Cloudinary)
test_image_url = "https://res.cloudinary.com/YOUR_CLOUD/image/upload/v123456789/product.jpg"

print(f"\n{'='*80}")
print(f"TEST: Multi-Crop Detection")
print(f"{'='*80}\n")

# Descomentar cuando tengas URL real:
# results = detect_categories_multi_crop(test_image_url, client.id, top_k=5)
#
# print(f"\n📊 RESULTADOS ({len(results)} categor\u00edas detectadas):\n")
# for i, r in enumerate(results, 1):
#     status = "✅" if r['passes_threshold'] else "❌"
#     print(f"{i}. {status} {r['category_name']:30s} score={r['score']:.3f} (best_crop={r['best_crop']})")
#     print(f"   Crop scores: {r['crop_scores']}")
#     print()

print("⚠️ Para ejecutar el test completo:")
print("   1. Descarga imágenes: python download_cloudinary_images.py")
print("   2. O usa URL directa de Cloudinary de un producto")
print("   3. Descomenta las líneas en el script")
