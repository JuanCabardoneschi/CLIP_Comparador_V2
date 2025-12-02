"""
Script para procesar embeddings de Test Clip en Railway
Ejecuta el proceso de generación de embeddings CLIP manualmente
"""
import sys
import os

# Configurar path
sys.path.insert(0, 'clip_admin_backend')
os.chdir('clip_admin_backend')

# Configurar environment para Railway
os.environ['DATABASE_URL'] = 'postgresql://postgres:xhinRHxDvcdHNqyQKDTUbDKRLhYNLDum@ballast.proxy.rlwy.net:54363/railway'

from app.services.tiendanube_sync_service import TiendanubeSyncService

CLIENT_ID = 'c41a8553-e465-463a-ad06-4490560fa8db'

if __name__ == '__main__':
    print(f"🚀 Procesando embeddings para Test Clip (ID: {CLIENT_ID})...")

    try:
        service = TiendanubeSyncService(CLIENT_ID)
        print(f"✅ Servicio inicializado")
        print(f"   Cliente: {service.client.name}")
        print(f"   Store: {service.integration.store_name}")

        print("\n📸 Generando embeddings CLIP...")
        service.generate_embeddings()

        print("\n📊 Calculando centroides de categorías...")
        service.calculate_category_centroids()

        print("\n✅ ¡Proceso completado exitosamente!")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
