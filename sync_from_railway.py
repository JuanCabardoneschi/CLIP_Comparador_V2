"""
Sincronización completa desde Railway a BD Local
Trae categorías, productos e imágenes nuevas y ejecuta pipeline completo de procesamiento.

Uso:
    python sync_from_railway.py --dry-run  # Ver qué se sincronizaría sin hacer cambios
    python sync_from_railway.py --yes      # Ejecutar sincronización completa
"""
import os
import sys

# Configurar encoding UTF-8 para evitar problemas con emojis en Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import json
import argparse
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

# Cargar entorno local
load_dotenv('.env.local')

# Setup path para imports de Flask
clip_backend_path = os.path.join(os.path.dirname(__file__), 'clip_admin_backend')
sys.path.insert(0, clip_backend_path)

# Import correcto
os.chdir(clip_backend_path)  # Cambiar al directorio del backend
from app import db
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from app.models.client import Client

# Importar create_app desde app.py (no desde el package app)
import importlib.util
spec = importlib.util.spec_from_file_location("app_module", os.path.join(clip_backend_path, "app.py"))
flask_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flask_app_module)
create_app = flask_app_module.create_app


def get_railway_conn():
    """Conexión a Railway DB"""
    host = os.getenv('RAILWAY_DB_HOST', 'ballast.proxy.rlwy.net')
    port = int(os.getenv('RAILWAY_DB_PORT', '54363'))
    database = os.getenv('RAILWAY_DB', 'railway')
    user = os.getenv('RAILWAY_DB_USER', 'postgres')
    password = os.getenv('RAILWAY_DB_PASSWORD', 'xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum')
    return psycopg2.connect(host=host, port=port, database=database, user=user, password=password)


def fetch_railway_data():
    """Obtener todos los datos desde Railway"""
    print("📡 Conectando a Railway...")

    with get_railway_conn() as conn:
        with conn.cursor() as cur:
            # Clients
            cur.execute("SELECT id, name, email, industry, api_key, created_at FROM clients ORDER BY created_at")
            clients_raw = cur.fetchall()
            clients = [dict(zip(['id', 'name', 'email', 'industry', 'api_key', 'created_at'], row)) for row in clients_raw]

            # Categories (sin vision_hint que no existe en Railway)
            cur.execute("""
                SELECT id, client_id, slug, name, name_en, alternative_terms, description,
                       clip_prompt, visual_features, confidence_threshold,
                       centroid_embedding, centroid_updated_at, centroid_image_count,
                       color, is_active, created_at, updated_at
                FROM categories
                ORDER BY client_id, created_at
            """)
            categories_raw = cur.fetchall()
            categories = [dict(zip(['id', 'client_id', 'slug', 'name', 'name_en', 'alternative_terms',
                                   'description', 'clip_prompt', 'visual_features',
                                   'confidence_threshold', 'centroid_embedding', 'centroid_updated_at',
                                   'centroid_image_count', 'color', 'is_active', 'created_at', 'updated_at'],
                                  row)) for row in categories_raw]

            # Products (sin name_en que no existe en Railway)
            cur.execute("""
                SELECT id, client_id, category_id, name, sku, description, price,
                       stock, is_active, attributes, created_at, updated_at
                FROM products
                ORDER BY client_id, created_at
            """)
            products_raw = cur.fetchall()
            products = [dict(zip(['id', 'client_id', 'category_id', 'name', 'sku',
                                 'description', 'price', 'stock', 'is_active', 'attributes',
                                 'created_at', 'updated_at'], row)) for row in products_raw]

            # Images (solo columnas básicas que seguro existen en Railway)
            cur.execute("""
                SELECT id, product_id, cloudinary_public_id, cloudinary_url,
                       is_primary, is_processed, upload_status, clip_embedding,
                       created_at, updated_at
                FROM images
                ORDER BY product_id, is_primary DESC, created_at
            """)
            images_raw = cur.fetchall()
            images = [dict(zip(['id', 'product_id', 'cloudinary_public_id', 'cloudinary_url',
                               'is_primary', 'is_processed', 'upload_status', 'clip_embedding',
                               'created_at', 'updated_at'], row)) for row in images_raw]

    print(f"✅ Datos obtenidos desde Railway:")
    print(f"   - Clientes: {len(clients)}")
    print(f"   - Categorías: {len(categories)}")
    print(f"   - Productos: {len(products)}")
    print(f"   - Imágenes: {len(images)}")

    return {
        'clients': clients,
        'categories': categories,
        'products': products,
        'images': images
    }


def sync_clients(railway_clients, dry_run=True):
    """Sincronizar clientes"""
    print("\n👥 Sincronizando clientes...")
    new_count = 0

    for rc in railway_clients:
        existing = Client.query.get(rc['id'])
        if not existing:
            print(f"  ➕ Nuevo cliente: {rc['name']} ({rc['email']})")
            if not dry_run:
                client = Client(
                    id=rc['id'],
                    name=rc['name'],
                    email=rc['email'],
                    industry=rc['industry'],
                    api_key=rc['api_key']
                )
                db.session.add(client)
            new_count += 1

    if not dry_run and new_count > 0:
        db.session.commit()
        print(f"✅ {new_count} cliente(s) creado(s)")
    else:
        print(f"ℹ️  {new_count} cliente(s) nuevo(s) detectado(s)")

    return new_count


def sync_categories(railway_categories, dry_run=True):
    """Sincronizar categorías"""
    print("\n📁 Sincronizando categorías...")
    new_count = 0

    for rc in railway_categories:
        existing = Category.query.get(rc['id'])
        if not existing:
            print(f"  ➕ Nueva categoría: {rc['name']} (Cliente: {rc['client_id'][:8]}...)")
            if not dry_run:
                category = Category(
                    id=rc['id'],
                    client_id=rc['client_id'],
                    slug=rc['slug'],
                    name=rc['name'],
                    name_en=rc.get('name_en'),  # Puede no existir
                    alternative_terms=rc.get('alternative_terms'),
                    description=rc.get('description'),
                    # vision_hint no existe en Railway, se deja NULL
                    clip_prompt=rc.get('clip_prompt'),
                    visual_features=rc.get('visual_features'),
                    confidence_threshold=rc.get('confidence_threshold'),
                    color=rc.get('color'),
                    is_active=rc.get('is_active', True)
                )
                db.session.add(category)
            new_count += 1

    if not dry_run and new_count > 0:
        db.session.commit()
        print(f"✅ {new_count} categoría(s) creada(s)")
    else:
        print(f"ℹ️  {new_count} categoría(s) nueva(s) detectada(s)")

    return new_count


def sync_products(railway_products, dry_run=True):
    """Sincronizar productos"""
    print("\n📦 Sincronizando productos...")
    new_count = 0

    for rp in railway_products:
        existing = Product.query.get(rp['id'])
        if not existing:
            print(f"  ➕ Nuevo producto: {rp['name']} (SKU: {rp['sku']})")
            if not dry_run:
                # Convertir attributes de JSON string a dict si viene como string
                attributes = rp['attributes']
                if isinstance(attributes, str):
                    try:
                        attributes = json.loads(attributes)
                    except:
                        attributes = {}

                product = Product(
                    id=rp['id'],
                    client_id=rp['client_id'],
                    category_id=rp['category_id'],
                    name=rp['name'],
                    sku=rp.get('sku'),
                    description=rp.get('description'),
                    price=rp.get('price'),
                    stock=rp['stock'],
                    is_active=rp['is_active'],
                    attributes=attributes
                )
                db.session.add(product)
            new_count += 1

    if not dry_run and new_count > 0:
        db.session.commit()
        print(f"✅ {new_count} producto(s) creado(s)")
    else:
        print(f"ℹ️  {new_count} producto(s) nuevo(s) detectado(s)")

    return new_count


def sync_images(railway_images, dry_run=True):
    """Sincronizar imágenes (solo metadata, las imágenes ya están en Cloudinary)"""
    print("\n🖼️  Sincronizando imágenes...")
    new_count = 0
    needs_processing = []

    for ri in railway_images:
        existing = Image.query.get(ri['id'])
        if not existing:
            print(f"  ➕ Nueva imagen: {ri['cloudinary_public_id']} (Producto: {ri['product_id'][:8]}...)")
            if not dry_run:
                # Extraer filename del cloudinary_public_id (última parte después del /)
                filename = ri['cloudinary_public_id'].split('/')[-1] if ri['cloudinary_public_id'] else 'image.jpg'

                # Obtener client_id del producto
                from app.models.product import Product
                product = Product.query.get(ri['product_id'])
                client_id = product.client_id if product else None

                image = Image(
                    id=ri['id'],
                    client_id=client_id,
                    product_id=ri['product_id'],
                    filename=filename,
                    cloudinary_public_id=ri['cloudinary_public_id'],
                    cloudinary_url=ri['cloudinary_url'],
                    is_primary=ri['is_primary'],
                    is_processed=False,  # Marcar como no procesada para forzar pipeline
                    upload_status='completed'
                )
                db.session.add(image)
                needs_processing.append(image.id)
            else:
                needs_processing.append(ri['id'])
            new_count += 1

    if not dry_run and new_count > 0:
        db.session.commit()
        print(f"✅ {new_count} imagen(es) creada(s)")
    else:
        print(f"ℹ️  {new_count} imagen(es) nueva(s) detectada(s)")

    return new_count, needs_processing


def process_new_images(image_ids, dry_run=True):
    """Ejecutar pipeline completo de procesamiento para imágenes nuevas"""
    if not image_ids or dry_run:
        print(f"\nℹ️  {len(image_ids)} imagen(es) necesitaría(n) procesamiento")
        return

    print(f"\n⚙️  Procesando {len(image_ids)} imagen(es) nueva(s)...")
    print("   Pipeline: Auto-crop → Embeddings CLIP → Detección atributos → Centroides")

    from app.blueprints.embeddings import generate_clip_embedding
    from app.services.image_manager import ImageManager

    image_manager = ImageManager()
    processed = 0
    errors = 0

    for img_id in image_ids:
        try:
            image = Image.query.get(img_id)
            if not image:
                continue

            print(f"\n  🔄 Procesando: {image.cloudinary_public_id}")

            # 1. Auto-crop (si aplica - detectar múltiples prendas)
            print(f"     1️⃣ Auto-crop...")
            # El crop se hace automáticamente en generate_clip_embedding si está habilitado

            # 2. Generar embedding CLIP
            print(f"     2️⃣ Generando embedding CLIP...")
            embedding, metadata = generate_clip_embedding(image.cloudinary_url, image)

            if embedding is not None:
                # Embedding puede venir como numpy array o lista
                if hasattr(embedding, 'tolist'):
                    image.clip_embedding = json.dumps(embedding.tolist())
                else:
                    image.clip_embedding = json.dumps(embedding)

                image.processing_metadata = json.dumps(metadata) if metadata else None
                image.is_processed = True
                image.upload_status = 'completed'

                # 3. Detección de atributos dinámicos (colores, etc.)
                print(f"     3️⃣ Detectando atributos...")
                product = image.product
                if product:
                    # Auto-detectar color principal si no tiene
                    if not product.attributes.get('color'):
                        from app.services.color_detector import detect_dominant_color
                        try:
                            color_data = detect_dominant_color(image.cloudinary_url)
                            if color_data:
                                if not product.attributes:
                                    product.attributes = {}
                                product.attributes['color'] = color_data.get('name', 'sin definir')
                                print(f"        ✅ Color detectado: {product.attributes['color']}")
                        except Exception as e:
                            print(f"        ⚠️ No se pudo detectar color: {e}")

                db.session.commit()
                processed += 1
                print(f"     ✅ Imagen procesada exitosamente")
            else:
                errors += 1
                print(f"     ❌ Error generando embedding")

        except Exception as e:
            errors += 1
            print(f"     ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    # 4. Recalcular centroides por categoría afectada
    print(f"\n  4️⃣ Recalculando centroides de categorías...")
    affected_categories = set()
    for img_id in image_ids:
        image = Image.query.get(img_id)
        if image and image.product and image.product.category_id:
            affected_categories.add(image.product.category_id)

    for cat_id in affected_categories:
        category = Category.query.get(cat_id)
        if category:
            print(f"     🔄 Actualizando centroide: {category.name}")
            category.update_centroid_embedding(force_recalculate=True)

    db.session.commit()

    print(f"\n✅ Pipeline completado:")
    print(f"   - Procesadas: {processed}")
    print(f"   - Errores: {errors}")
    print(f"   - Categorías actualizadas: {len(affected_categories)}")


def main():
    parser = argparse.ArgumentParser(description='Sincronizar desde Railway a BD Local')
    parser.add_argument('--yes', action='store_true', help='Ejecutar cambios (sin esto solo muestra qué haría)')
    parser.add_argument('--dry-run', action='store_true', help='Modo simulación (equivalente a no usar --yes)')
    args = parser.parse_args()

    dry_run = not args.yes or args.dry_run

    if dry_run:
        print("🛟 MODO DRY-RUN: Solo se mostrará qué se sincronizaría, sin hacer cambios")
        print("   Usa --yes para ejecutar la sincronización real\n")
    else:
        print("⚠️  MODO EJECUCIÓN: Se aplicarán todos los cambios")
        print("   Presiona Ctrl+C en los próximos 3 segundos para cancelar...\n")
        import time
        time.sleep(3)

    # Crear app context
    app = flask_app_module.create_app()
    with app.app_context():
        # 1. Fetch data from Railway
        railway_data = fetch_railway_data()

        # 2. Sync in order: clients → categories → products → images
        sync_clients(railway_data['clients'], dry_run)
        sync_categories(railway_data['categories'], dry_run)
        sync_products(railway_data['products'], dry_run)
        new_images, image_ids = sync_images(railway_data['images'], dry_run)

        # 3. Process new images (embeddings, crops, attributes, centroids)
        if image_ids:
            process_new_images(image_ids, dry_run)

        print("\n" + "="*60)
        if dry_run:
            print("✅ DRY-RUN COMPLETADO - No se hicieron cambios")
            print("   Ejecuta con --yes para aplicar la sincronización")
        else:
            print("✅ SINCRONIZACIÓN COMPLETADA")
        print("="*60)


if __name__ == '__main__':
    main()
