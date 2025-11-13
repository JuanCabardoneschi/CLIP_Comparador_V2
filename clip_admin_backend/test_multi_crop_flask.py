"""
Script de test para multi-crop detection
Ejecutar: flask shell < test_multi_crop_flask.py
"""
from app import db
from app.models.client import Client
from app.models.product import Product
from app.blueprints.embeddings import detect_categories_multi_crop

# Buscar cliente
client = Client.query.filter_by(name="Goody Store").first()
if not client:
    print("❌ Cliente no encontrado")
    exit()

print(f"\n{'='*80}")
print(f"✅ Cliente: {client.name}")
print(f"   ID: {client.id}")
print(f"   Threshold: {client.category_confidence_threshold}%")
print(f"{'='*80}\n")

# Buscar producto con imagen
product = Product.query.filter_by(
    client_id=client.id,
    is_active=True
).first()

if not product or not product.images:
    print("⚠️ No hay productos con imágenes para testear")
    print("\nPara testear:")
    print("1. Agrega productos al cliente 'Goody Store' en admin panel")
    print("2. O ejecuta manualmente con:")
    print("   from app.blueprints.embeddings import detect_categories_multi_crop")
    print("   results = detect_categories_multi_crop('URL_CLOUDINARY', 'CLIENT_ID')")
    exit()

image = product.images[0]
image_url = image.display_url

print(f"🖼️  Producto: {product.name}")
print(f"   Categoría: {product.category.name if product.category else 'N/A'}")
print(f"   Imagen: {image_url[:80]}...")
print(f"\n{'='*80}")
print(f"EJECUTANDO DETECCIÓN MULTI-CROP...")
print(f"{'='*80}\n")

# Ejecutar detección
try:
    results = detect_categories_multi_crop(image_url, client.id, top_k=5)

    print(f"\n📊 RESULTADOS ({len(results)} categorías detectadas):\n")
    for i, r in enumerate(results, 1):
        status = "✅" if r['passes_threshold'] else "❌"
        print(f"{i}. {status} {r['category_name']:30s} score={r['score']:.3f}")
        print(f"   Best crop: {r['best_crop']}")
        crop_scores_str = ', '.join([f"{k}={v:.2f}" for k,v in r['crop_scores'].items()])
        print(f"   Crop scores: {crop_scores_str}")
        print()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
