"""
Script para Recalcular Centroides con BLIP-2
Regenera todos los centroides de categorías usando embeddings BLIP-2

Uso:
    python recalculate_blip2_centroids.py [--client-id CLIENT_ID] [--force]
"""

import sys
from pathlib import Path

# Configurar path
sys.path.insert(0, str(Path(__file__).parent / 'clip_admin_backend'))

from app import create_app, db
from app.models.category import Category
from app.models.client import Client

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def recalculate_centroids(client_id=None, force=False):
    """
    Recalcula centroides para todas las categorías.

    Args:
        client_id: Solo procesar este cliente (None = todos)
        force: Forzar recálculo aunque ya existan centroides

    Returns:
        dict: Estadísticas del proceso
    """
    app = create_app()

    with app.app_context():
        logger.info("🔄 Recalculando centroides con embeddings BLIP-2...")

        # Usar método de clase de Category
        stats = Category.recalculate_all_centroids(
            client_id=client_id,
            force=force
        )

        logger.info("\n" + "="*60)
        logger.info("📊 RESULTADOS")
        logger.info("="*60)
        logger.info(f"Total categorías:   {stats['total']}")
        logger.info(f"Actualizadas:       {stats['updated']}")
        logger.info(f"Saltadas:           {stats['skipped']}")
        logger.info(f"Errores:            {stats['errors']}")
        logger.info("="*60 + "\n")

        return stats


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description='Recalcular centroides con BLIP-2')
    parser.add_argument('--client-id', type=str, help='ID del cliente (opcional)')
    parser.add_argument('--force', action='store_true', help='Forzar recálculo de todos los centroides')

    args = parser.parse_args()

    logger.info("🚀 INICIANDO RECÁLCULO DE CENTROIDES\n")

    try:
        stats = recalculate_centroids(
            client_id=args.client_id,
            force=args.force
        )

        if stats['errors'] == 0:
            logger.info("✅ Recálculo completado exitosamente!")
        else:
            logger.warning(f"⚠️ Completado con {stats['errors']} errores")

    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
