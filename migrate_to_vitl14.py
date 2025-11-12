"""
Script de Migración a CLIP ViT-L/14
=====================================

Regenera todos los embeddings de imágenes y centroides de categorías
usando el nuevo modelo CLIP ViT-L/14 (768D vs 512D anterior).

IMPORTANTE:
- Hace backup automático de la DB antes de proceder
- Requiere Railway Pro ($20/mes) para producción (3GB RAM modelo)
- En local funciona sin problema

Uso:
    python migrate_to_vitl14.py [--client CLIENT_ID] [--dry-run] [--force]
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "clip_admin_backend"))

from app import create_app, db
from app.models.image import Image
from app.models.category import Category
from app.models.client import Client
from app.blueprints.embeddings import get_clip_model, load_image_from_source
import torch
import numpy as np
from tqdm import tqdm


def backup_database():
    """Crear backup de la DB antes de migración"""
    print("\n📦 Creando backup de seguridad...")

    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"pre_vitl14_migration_{timestamp}.sql"

    # Detectar si es local o Railway
    db_url = os.getenv("DATABASE_URL", "")

    if "localhost" in db_url or "127.0.0.1" in db_url:
        # Backup local con pg_dump
        os.system(f'pg_dump -U postgres -d clip_comparador_v2_local > "{backup_file}"')
    else:
        print("⚠️  Para Railway, usa: python railway_db_tool.py backup")
        return None

    if backup_file.exists():
        print(f"✅ Backup creado: {backup_file}")
        return backup_file
    else:
        print("❌ Error creando backup")
        return None


def generate_embedding_vitl14(image_url, model, processor):
    """Generar embedding con ViT-L/14 (768D)"""
    try:
        # Cargar imagen desde Cloudinary
        image = load_image_from_source(image_url)

        # Procesar con CLIP ViT-L/14
        inputs = processor(images=image, return_tensors="pt")

        with torch.no_grad():
            image_features = model.get_image_features(**inputs)
            # Normalizar
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            embedding = image_features.cpu().numpy().flatten()

        return embedding.tolist()

    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None


def migrate_client_images(client_id, dry_run=False, force=False):
    """Migrar embeddings de un cliente específico"""

    app = create_app()

    with app.app_context():
        # Verificar cliente
        client = Client.query.get(client_id)
        if not client:
            print(f"❌ Cliente {client_id} no encontrado")
            return

        print(f"\n🏢 Cliente: {client.name} (ID: {client.id})")

        # Obtener imágenes del cliente
        images = Image.query.join(Image.product).filter(
            Image.product.has(client_id=client_id),
            Image.is_processed == True,
            Image.clip_embedding.isnot(None)
        ).all()

        if not images:
            print("⚠️  No hay imágenes para migrar")
            return

        print(f"📸 Encontradas {len(images)} imágenes para migrar")

        # Verificar dimensión actual
        sample_img = images[0]
        try:
            current_emb = json.loads(sample_img.clip_embedding)
            current_dim = len(current_emb)
            print(f"📊 Dimensión actual: {current_dim}D")

            if current_dim == 768 and not force:
                print("✅ Las imágenes ya están en 768D (ViT-L/14)")
                response = input("¿Regenerar de todas formas? (s/N): ")
                if response.lower() != 's':
                    return
        except:
            pass

        if dry_run:
            print("\n🔍 MODO DRY-RUN - No se harán cambios")
            print(f"Se regenerarían {len(images)} embeddings de {current_dim}D → 768D")
            return

        # Cargar modelo ViT-L/14
        print("\n🔄 Cargando CLIP ViT-L/14...")
        model, processor = get_clip_model()
        print("✅ Modelo cargado")

        # Migrar embeddings
        print("\n🔄 Regenerando embeddings...")
        success_count = 0
        error_count = 0

        for image in tqdm(images, desc="Procesando imágenes"):
            try:
                # Generar nuevo embedding 768D
                new_embedding = generate_embedding_vitl14(
                    image.display_url, model, processor
                )

                if new_embedding:
                    # Actualizar en DB
                    image.clip_embedding = json.dumps(new_embedding)
                    image.updated_at = datetime.utcnow()
                    db.session.add(image)
                    success_count += 1
                else:
                    error_count += 1

                # Commit cada 50 imágenes
                if success_count % 50 == 0:
                    db.session.commit()

            except Exception as e:
                print(f"\n❌ Error en imagen {image.id}: {e}")
                error_count += 1
                continue

        # Commit final
        db.session.commit()

        print(f"\n✅ Migración completada:")
        print(f"   - Exitosas: {success_count}")
        print(f"   - Errores: {error_count}")

        # Recalcular centroides
        print("\n🎯 Recalculando centroides de categorías...")
        categories = Category.query.filter_by(client_id=client_id).all()

        for category in tqdm(categories, desc="Actualizando centroides"):
            try:
                category.update_centroid_embedding(force_recalculate=True)
                db.session.commit()
            except Exception as e:
                print(f"\n❌ Error actualizando centroide de {category.name}: {e}")

        print("\n✅ Centroides actualizados")


def main():
    parser = argparse.ArgumentParser(description="Migrar embeddings a CLIP ViT-L/14")
    parser.add_argument("--client", help="ID del cliente a migrar (o 'all' para todos)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin hacer cambios")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración aunque ya sea 768D")
    parser.add_argument("--no-backup", action="store_true", help="Saltar backup (NO RECOMENDADO)")

    args = parser.parse_args()

    print("=" * 60)
    print("   MIGRACIÓN A CLIP ViT-L/14 (768D)")
    print("=" * 60)

    # Backup
    if not args.no_backup and not args.dry_run:
        backup_file = backup_database()
        if not backup_file:
            response = input("\n⚠️  No se pudo crear backup. ¿Continuar de todas formas? (s/N): ")
            if response.lower() != 's':
                print("❌ Migración cancelada")
                return

    # Migrar
    if args.client:
        if args.client.lower() == 'all':
            app = create_app()
            with app.app_context():
                clients = Client.query.all()
                print(f"\n🌍 Migrando TODOS los clientes ({len(clients)})")

                for client in clients:
                    migrate_client_images(str(client.id), args.dry_run, args.force)
        else:
            migrate_client_images(args.client, args.dry_run, args.force)
    else:
        print("\n❌ Debes especificar --client CLIENT_ID o --client all")
        print("\nEjemplo: python migrate_to_vitl14.py --client all")
        print("         python migrate_to_vitl14.py --client <UUID> --dry-run")


if __name__ == "__main__":
    main()
