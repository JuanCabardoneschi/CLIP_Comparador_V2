"""Borrado manual de categorías en Railway.

Elimina categorías por nombre EXACTO (no contiene/parcial), sus productos e imágenes,
incluyendo la eliminación de imágenes en Cloudinary.

Uso:
    python delete_categories_railway.py --names pantalones remeras --yes

Opcional:
    --client-id <uuid>  Limita borrado a un cliente específico (recomendado en multi-tenant)
    --dry-run           Muestra lo que se borraría sin ejecutar

Notas:
    - SOLO nombres exactos.
    - Cloudinary: requiere que CLOUDINARY_URL esté configurado en el entorno.
    - Cada categoría se procesa de forma aislada (commit independiente) para reducir riesgo.
    - Si una imagen no puede eliminarse de Cloudinary se continúa y se elimina el registro igualmente.
"""

import os
import sys
import argparse
from typing import List

import cloudinary
import cloudinary.uploader

# Asegurar path para importar backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIP_BACKEND_DIR = os.path.join(BASE_DIR, 'clip_admin_backend')
if CLIP_BACKEND_DIR not in sys.path:
    sys.path.insert(0, CLIP_BACKEND_DIR)

from app import db  # type: ignore
from app.models.category import Category  # type: ignore
from app.models.product import Product  # type: ignore
from app.models.image import Image  # type: ignore
from app import create_app  # type: ignore


def parse_args():
    parser = argparse.ArgumentParser(description="Eliminar categorías en Railway por nombre exacto")
    parser.add_argument('--names', nargs='+', required=True,
                        help='Lista de nombres EXACTOS de categorías a eliminar')
    parser.add_argument('--client-id', dest='client_id', default=None,
                        help='Filtrar por client_id específico (UUID)')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar acciones sin ejecutar cambios')
    parser.add_argument('--yes', action='store_true', help='Saltarse confirmación interactiva')
    return parser.parse_args()


def find_categories(names: List[str], client_id: str | None):
    query = Category.query.filter(Category.name.in_(names))
    if client_id:
        query = query.filter(Category.client_id == client_id)
    categories = query.all()
    # Filtrar solo nombres exactos (case sensitive por seguridad)
    filtered = [c for c in categories if c.name in names]
    return filtered


def delete_category(category: Category, dry_run: bool = False):
    print(f"\n=== Procesando categoría: {category.name} ({category.id}) Cliente: {category.client_id} ===")

    # Obtener productos
    products = Product.query.filter_by(category_id=category.id).all()
    print(f"Productos encontrados: {len(products)}")

    # Recolectar imágenes
    product_ids = [p.id for p in products]
    images = []
    if product_ids:
        images = Image.query.filter(Image.product_id.in_(product_ids)).all()
    print(f"Imágenes encontradas: {len(images)}")

    if dry_run:
        print("[DRY-RUN] No se ejecutará eliminación.")
        return

    # Eliminar imágenes en Cloudinary
    cloud_success = 0
    cloud_fail = 0
    for img in images:
        if img.cloudinary_public_id:
            try:
                result = cloudinary.uploader.destroy(img.cloudinary_public_id)
                if result.get('result') == 'ok':
                    cloud_success += 1
                    print(f"🗑️  Cloudinary OK: {img.cloudinary_public_id}")
                else:
                    cloud_fail += 1
                    print(f"⚠️  Cloudinary FAIL: {img.cloudinary_public_id} -> {result}")
            except Exception as e:
                cloud_fail += 1
                print(f"❌  Cloudinary EXC: {img.cloudinary_public_id} -> {e}")

    # Eliminar registros de imágenes
    for img in images:
        db.session.delete(img)

    # Eliminar productos
    for p in products:
        db.session.delete(p)

    # Eliminar categoría
    db.session.delete(category)

    # Commit parcial
    db.session.commit()
    print(f"✅ Categoría '{category.name}' eliminada. Productos: {len(products)}, Imágenes: {len(images)}, Cloudinary OK: {cloud_success}, Cloudinary Errores: {cloud_fail}")


def main():
    args = parse_args()

    app = create_app()
    with app.app_context():
        print("🔍 Buscando categorías...")
        categories = find_categories(args.names, args.client_id)
        if not categories:
            print("❌ No se encontraron categorías con esos nombres.")
            return

        print("Encontradas:")
        for c in categories:
            prod_count = Product.query.filter_by(category_id=c.id).count()
            img_count = Image.query.join(Product, Image.product_id == Product.id) \
                               .filter(Product.category_id == c.id).count()
            cid = str(c.id)
            clid = str(c.client_id)
            print(f" - {c.name} (ID: {cid[:8]}..., Cliente: {clid[:8]}..., Productos: {prod_count}, Imágenes: {img_count})")

        if args.dry_run:
            print("[DRY-RUN] Fin sin cambios.")
            return

        if not args.yes:
            confirm = input("¿Confirmar eliminación de TODAS las categorías listadas? (escribe 'SI' para continuar): ").strip()
            if confirm.upper() != 'SI':
                print("Operación cancelada.")
                return

        for cat in categories:
            delete_category(cat, dry_run=False)

        print("\n🎯 Proceso completado.")


if __name__ == '__main__':
    main()
