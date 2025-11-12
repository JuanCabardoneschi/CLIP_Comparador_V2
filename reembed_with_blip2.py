"""
Script de Re-embedding Masivo con BLIP-2
Re-genera todos los embeddings de imágenes del catálogo usando BLIP-2

IMPORTANTE:
- Hace backup automático de la BD antes de comenzar
- Sobrescribe campo clip_embedding con embeddings BLIP-2 (256D)
- Mantiene compatibilidad con estructura existente
- Progress tracking con logging detallado

Uso:
    python reembed_with_blip2.py [--client-id CLIENT_ID] [--dry-run]
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

# Configurar path para imports
sys.path.insert(0, str(Path(__file__).parent / 'clip_admin_backend'))

# Imports de la app
from app import create_app, db
from app.models.image import Image
from app.models.product import Product
from app.models.category import Category
from app.models.client import Client
from app.utils.blip2_embeddings import get_blip2_system
from app.services.image_manager import image_manager

# Configurar logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'reembed_blip2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def backup_database():
    """Crea backup de la BD antes de comenzar"""
    try:
        logger.info("📦 Creando backup de base de datos...")

        from subprocess import run
        import subprocess

        backup_file = f"backups/local_before_blip2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dump"

        # Crear directorio si no existe
        Path("backups").mkdir(exist_ok=True)

        # Obtener credenciales de .env.local
        from dotenv import load_dotenv
        load_dotenv('.env.local')

        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.warning("⚠️ DATABASE_URL no encontrado, saltando backup")
            return None

        # Ejecutar pg_dump
        result = run(
            f'pg_dump "{db_url}" > {backup_file}',
            shell=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info(f"✅ Backup creado: {backup_file}")
            return backup_file
        else:
            logger.warning(f"⚠️ Error en backup: {result.stderr}")
            return None

    except Exception as e:
        logger.warning(f"⚠️ No se pudo crear backup: {e}")
        return None


def reembed_images(client_id=None, dry_run=False, batch_size=10):
    """
    Re-embeda todas las imágenes con BLIP-2.

    Args:
        client_id: Solo procesar imágenes de este cliente (None = todos)
        dry_run: Si True, no guarda cambios en BD
        batch_size: Número de imágenes por batch

    Returns:
        dict: Estadísticas del proceso
    """
    app = create_app()

    with app.app_context():
        # Estadísticas
        stats = {
            'total': 0,
            'processed': 0,
            'errors': 0,
            'skipped': 0,
            'start_time': time.time()
        }

        # Query de imágenes
        query = db.session.query(Image).join(Product).join(Category).join(Client)

        if client_id:
            query = query.filter(Client.id == client_id)
            logger.info(f"🎯 Procesando solo cliente: {client_id}")

        # Solo imágenes activas y con cloudinary_public_id
        query = query.filter(
            Image.is_active == True,
            Image.cloudinary_public_id.isnot(None)
        )

        images = query.all()
        stats['total'] = len(images)

        logger.info(f"🔄 Total de imágenes a procesar: {stats['total']}")

        if dry_run:
            logger.info("🏃 Modo DRY RUN - no se guardarán cambios")

        # Cargar BLIP-2
        logger.info("🚀 Cargando BLIP-2...")
        blip2 = get_blip2_system()
        logger.info("✅ BLIP-2 cargado")

        # Procesar en batches
        for i, image in enumerate(images):
            try:
                logger.info(f"[{i+1}/{stats['total']}] Procesando imagen {image.id}")

                # Obtener URL de la imagen
                image_url = image.display_url
                if not image_url:
                    logger.warning(f"⚠️ Imagen {image.id} sin URL, saltando")
                    stats['skipped'] += 1
                    continue

                # Descargar imagen
                from PIL import Image as PILImage
                import requests
                from io import BytesIO

                response = requests.get(image_url, timeout=10)
                response.raise_for_status()

                pil_image = PILImage.open(BytesIO(response.content)).convert('RGB')

                # Generar embedding con BLIP-2
                start_time = time.time()
                embedding_array = blip2.encode_image(pil_image)
                embedding_time = time.time() - start_time

                # Convertir a lista y JSON
                embedding_list = embedding_array.tolist()
                embedding_json = json.dumps(embedding_list)

                # Actualizar en BD
                if not dry_run:
                    image.clip_embedding = embedding_json
                    image.is_processed = True
                    image.updated_at = datetime.utcnow()

                stats['processed'] += 1

                logger.info(f"✅ Imagen {image.id}: {embedding_time:.2f}s, dim={len(embedding_list)}")

                # Commit cada N imágenes
                if not dry_run and (i + 1) % batch_size == 0:
                    db.session.commit()
                    logger.info(f"💾 Batch commit: {stats['processed']} imágenes guardadas")

            except Exception as e:
                logger.error(f"❌ Error procesando imagen {image.id}: {e}")
                stats['errors'] += 1

                if not dry_run:
                    db.session.rollback()

        # Commit final
        if not dry_run:
            try:
                db.session.commit()
                logger.info("💾 Commit final completado")
            except Exception as e:
                logger.error(f"❌ Error en commit final: {e}")
                db.session.rollback()

        # Estadísticas finales
        stats['elapsed_time'] = time.time() - stats['start_time']
        stats['avg_time_per_image'] = stats['elapsed_time'] / stats['processed'] if stats['processed'] > 0 else 0

        logger.info("\n" + "="*60)
        logger.info("📊 ESTADÍSTICAS FINALES")
        logger.info("="*60)
        logger.info(f"Total imágenes:     {stats['total']}")
        logger.info(f"Procesadas:         {stats['processed']}")
        logger.info(f"Errores:            {stats['errors']}")
        logger.info(f"Saltadas:           {stats['skipped']}")
        logger.info(f"Tiempo total:       {stats['elapsed_time']/60:.2f} minutos")
        logger.info(f"Tiempo promedio:    {stats['avg_time_per_image']:.2f}s por imagen")
        logger.info("="*60 + "\n")

        return stats


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Re-embedding masivo con BLIP-2')
    parser.add_argument('--client-id', type=str, help='ID del cliente (opcional)')
    parser.add_argument('--dry-run', action='store_true', help='No guardar cambios')
    parser.add_argument('--batch-size', type=int, default=10, help='Tamaño de batch (default: 10)')
    parser.add_argument('--skip-backup', action='store_true', help='Saltar backup automático')

    args = parser.parse_args()

    logger.info("🚀 INICIANDO RE-EMBEDDING MASIVO CON BLIP-2")
    logger.info(f"Timestamp: {datetime.now().isoformat()}\n")

    # Crear backup
    if not args.skip_backup and not args.dry_run:
        backup_file = backup_database()
        if backup_file:
            logger.info(f"✅ Backup guardado: {backup_file}\n")

    # Confirmar antes de proceder
    if not args.dry_run:
        response = input("⚠️  Este proceso SOBRESCRIBIRÁ todos los embeddings existentes. ¿Continuar? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("❌ Proceso cancelado por el usuario")
            return

    # Ejecutar re-embedding
    try:
        stats = reembed_images(
            client_id=args.client_id,
            dry_run=args.dry_run,
            batch_size=args.batch_size
        )

        logger.info("✅ Re-embedding completado exitosamente!")

        if stats['errors'] > 0:
            logger.warning(f"⚠️ Se encontraron {stats['errors']} errores - revisar log")

    except KeyboardInterrupt:
        logger.info("\n❌ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
