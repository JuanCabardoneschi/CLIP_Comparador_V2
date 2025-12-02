"""
Script para disparar sincronización manual de Tiendanube
"""
import sys
sys.path.insert(0, 'clip_admin_backend')

from app.services.tiendanube_sync_service import start_full_sync

# Cliente Test Clip
CLIENT_ID = 'e8c4a5b5-7402-4fdd-beb6-53fb7d84d2a6'  # Obtendremos esto de la DB

if __name__ == '__main__':
    print("🚀 Iniciando sincronización de Test Clip...")
    result = start_full_sync(CLIENT_ID)

    if result.get('success'):
        print("\n✅ Sincronización completada!")
        print(f"   Duración: {result.get('duration_seconds'):.2f}s")
        print(f"   Stats: {result.get('stats')}")
    else:
        print(f"\n❌ Error: {result.get('error')}")
        print(f"   Stats parciales: {result.get('stats')}")
