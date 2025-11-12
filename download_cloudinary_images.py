"""Script para descargar todas las imágenes de Cloudinary organizadas por categoría.

Descarga las imágenes del cliente Goody Store y las organiza en:
imagenes_goodystore/
  ├── CATEGORIA_1/
  │   ├── producto_001.jpg
  │   └── producto_002.jpg
  ├── CATEGORIA_2/
  └── ...
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Configurar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

# Cargar variables de entorno
env_local_path = Path(__file__).parent / '.env.local'
if env_local_path.exists():
    load_dotenv(env_local_path)
    print(f"Configuracion cargada desde {env_local_path}")
else:
    print("ADVERTENCIA: .env.local no encontrado")
    sys.exit(1)

# Inicializar Flask app para acceder a modelos
from app import create_app, db
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image

CLIENT_ID = '60231500-ca6f-4c46-a960-2e17298fcdb0'  # Goody Store
OUTPUT_DIR = Path(__file__).parent / 'imagenes_goodystore'


def sanitize_filename(name: str) -> str:
    """Sanitiza nombre para usar como carpeta/archivo."""
    # Reemplazar caracteres problemáticos
    replacements = {
        ' ': '_',
        '/': '-',
        '\\': '-',
        ':': '-',
        '*': '',
        '?': '',
        '"': '',
        '<': '',
        '>': '',
        '|': '',
        'Ñ': 'N',
        'ñ': 'n',
        'á': 'a',
        'é': 'e',
        'í': 'i',
        'ó': 'o',
        'ú': 'u',
        'Á': 'A',
        'É': 'E',
        'Í': 'I',
        'Ó': 'O',
        'Ú': 'U'
    }

    result = name
    for old, new in replacements.items():
        result = result.replace(old, new)

    # Eliminar caracteres no ASCII restantes
    result = ''.join(c for c in result if ord(c) < 128)

    return result.strip('_-')


def download_image(url: str, output_path: Path) -> bool:
    """Descarga una imagen desde URL y la guarda en output_path."""
    try:
        print(f"  Descargando: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"  OK: {output_path.name}")
        return True

    except Exception as e:
        print(f"  ERROR descargando {url}: {e}")
        return False


def main():
    """Función principal."""
    print("=" * 80)
    print("DESCARGA DE IMAGENES DE CLOUDINARY")
    print("=" * 80)
    print(f"Cliente: Goody Store ({CLIENT_ID})")
    print(f"Destino: {OUTPUT_DIR}")
    print("=" * 80)

    # Crear Flask app
    app = create_app()

    with app.app_context():
        # Obtener categorías del cliente
        categories = Category.query.filter_by(
            client_id=CLIENT_ID,
            is_active=True
        ).all()

        print(f"\nCategorias encontradas: {len(categories)}")

        total_images = 0
        downloaded = 0
        failed = 0

        for category in categories:
            cat_name = sanitize_filename(category.name)
            cat_dir = OUTPUT_DIR / cat_name

            print(f"\n--- CATEGORIA: {category.name} ---")

            # Obtener productos de esta categoría
            products = Product.query.filter_by(
                client_id=CLIENT_ID,
                category_id=category.id
            ).all()

            print(f"Productos: {len(products)}")

            for product in products:
                # Obtener imágenes del producto
                images = Image.query.filter_by(product_id=product.id).all()

                for idx, image in enumerate(images):
                    total_images += 1

                    # Generar nombre de archivo
                    product_name = sanitize_filename(product.name)
                    ext = '.jpg'  # Default

                    if image.cloudinary_public_id:
                        # Intentar obtener extensión del public_id
                        if '.' in image.cloudinary_public_id:
                            ext = '.' + image.cloudinary_public_id.split('.')[-1]

                    filename = f"{product_name}_{idx+1}{ext}"
                    output_path = cat_dir / filename

                    # Obtener URL de la imagen
                    url = image.display_url

                    if not url:
                        print(f"  SKIP: {product.name} - sin URL")
                        failed += 1
                        continue

                    # Descargar
                    if download_image(url, output_path):
                        downloaded += 1
                    else:
                        failed += 1

        print("\n" + "=" * 80)
        print("RESUMEN")
        print("=" * 80)
        print(f"Total imagenes: {total_images}")
        print(f"Descargadas: {downloaded}")
        print(f"Fallidas: {failed}")
        print(f"Directorio: {OUTPUT_DIR}")
        print("=" * 80)


if __name__ == '__main__':
    main()
