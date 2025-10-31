"""
Script de migración: Crear tabla color_mappings y aprender de productos existentes

Este script:
1. Crea la tabla color_mappings
2. Analiza todos los productos existentes
3. Aprende automáticamente los colores de cada cliente
"""
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Cargar la app Flask desde el archivo clip_admin_backend/app.py evitando el conflicto con el paquete app/
import importlib.util
_app_py_path = os.path.join(os.path.dirname(__file__), '..', 'clip_admin_backend', 'app.py')
_app_py_path = os.path.abspath(_app_py_path)
spec = importlib.util.spec_from_file_location("clip_backend_app_module", _app_py_path)
clip_backend_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clip_backend_app_module)

# Obtener create_app y db desde el módulo cargado
app = clip_backend_app_module.app  # usar la instancia ya creada por app.py
from app import db  # ahora que la app cargó el paquete, podemos importar db del paquete app
from clip_admin_backend.app.models import ColorMapping
from clip_admin_backend.app.services.color_learning_service import ColorLearningService
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Ejecuta la migración completa"""
    with app.app_context():
        logger.info("🚀 Iniciando migración de Color Learning System...")

        # 1. Crear tabla
        logger.info("📊 Creando tabla color_mappings...")
        create_table()

        # 2. Aprender de productos existentes
        logger.info("🎨 Analizando productos existentes...")
        learn_from_existing_products()

        logger.info("✅ Migración completada exitosamente")


def create_table():
    """Crea la tabla color_mappings y sus índices"""
    sql_file = os.path.join(
        os.path.dirname(__file__),
        '2025-10-30_color_learning_system.sql'
    )

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Asegurar extensión para UUID si es necesario
    try:
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        db.session.commit()
        logger.info("🔌 Extensión pgcrypto verificada/instalada")
    except Exception as e:
        logger.warning(f"⚠️  No se pudo verificar/instalar pgcrypto: {e}")

    # Ejecutar SQL
    db.session.execute(text(sql_content))
    db.session.commit()

    logger.info("✅ Tabla color_mappings creada")


def learn_from_existing_products():
    """
    Analiza todos los productos existentes y aprende sus colores.
    Esto permite que el sistema tenga datos iniciales sin esperar
    a que se creen nuevos productos.
    """
    # Obtener todos los productos con color vía SQL directo (evitar conflictos de ORM)
    query_sql = text(
        """
        SELECT id, client_id,
               COALESCE(attributes->>'color', attributes->>'Color') AS color
        FROM products
        WHERE attributes IS NOT NULL
          AND (attributes ? 'color' OR attributes ? 'Color')
        """
    )
    rows = db.session.execute(query_sql).fetchall()

    clients_stats = {}
    total_colors = 0

    for row in rows:
        color = row.color
        client_id = row.client_id

        # Procesar color con el servicio
        result = ColorLearningService.process_color(
            client_id=client_id,
            raw_color=color,
            auto_group=True
        )

        if result:
            total_colors += 1

            # Estadísticas por cliente
            if client_id not in clients_stats:
                clients_stats[client_id] = {
                    'total': 0,
                    'new': 0,
                    'existing': 0
                }

            clients_stats[client_id]['total'] += 1
            if result['is_new']:
                clients_stats[client_id]['new'] += 1
            else:
                clients_stats[client_id]['existing'] += 1

    # Mostrar estadísticas
    logger.info(f"\n📈 Estadísticas de aprendizaje:")
    logger.info(f"   Total de colores procesados: {total_colors}")
    logger.info(f"   Clientes con colores: {len(clients_stats)}")

    for client_id, stats in clients_stats.items():
        logger.info(f"\n   Cliente {client_id}:")
        logger.info(f"      - Colores únicos aprendidos: {stats['new']}")
        logger.info(f"      - Colores duplicados: {stats['existing']}")

        # Nota: omitir detalle de grupos para evitar conflictos ORM en contexto de script


if __name__ == '__main__':
    run_migration()
