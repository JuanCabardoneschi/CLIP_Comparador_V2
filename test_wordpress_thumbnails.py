"""
Verificar que las URLs de thumbnails 300x300 de WordPress existen
"""
import requests

# Ejemplo de URL original de WooCommerce/WordPress
test_urls = [
    "https://goodyshop.com.ar/wp-content/uploads/2024/12/Chaqueta-Chef-Panko-Negra.jpg",
    "https://goodyshop.com.ar/wp-content/uploads/2024/01/some-product.jpg"
]

def get_wordpress_thumbnail_url(original_url: str) -> str:
    """Convierte URL original a thumbnail 300x300"""
    if '-scaled' in original_url:
        original_url = original_url.replace('-scaled', '')

    parts = original_url.rsplit('.', 1)
    if len(parts) != 2:
        return original_url

    base_url, extension = parts
    thumbnail_url = f"{base_url}-300x300.{extension}"

    return thumbnail_url

print("🔍 VERIFICANDO THUMBNAILS DE WORDPRESS\n")

for original_url in test_urls:
    print(f"Original: {original_url}")

    # Verificar si original existe
    try:
        resp_original = requests.head(original_url, timeout=10, verify=True)
        original_exists = resp_original.status_code == 200
        original_size = resp_original.headers.get('content-length', 'desconocido')
        print(f"  ✅ Original existe ({original_size} bytes)")
    except Exception as e:
        original_exists = False
        print(f"  ❌ Original no accesible: {e}")

    # Generar URL de thumbnail
    thumbnail_url = get_wordpress_thumbnail_url(original_url)
    print(f"Thumbnail 300x300: {thumbnail_url}")

    # Verificar si thumbnail existe
    try:
        resp_thumb = requests.head(thumbnail_url, timeout=10, verify=True)
        thumb_exists = resp_thumb.status_code == 200
        thumb_size = resp_thumb.headers.get('content-length', 'desconocido')

        if thumb_exists:
            print(f"  ✅ Thumbnail existe ({thumb_size} bytes)")

            # Calcular reducción de tamaño
            if original_size != 'desconocido' and thumb_size != 'desconocido':
                reduction = ((int(original_size) - int(thumb_size)) / int(original_size)) * 100
                print(f"  📊 Reducción: {reduction:.1f}%")
        else:
            print(f"  ❌ Thumbnail NO existe (status {resp_thumb.status_code})")
    except Exception as e:
        print(f"  ❌ Thumbnail no accesible: {e}")

    print()
