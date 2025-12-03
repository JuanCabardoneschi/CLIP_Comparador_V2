"""
Script para disparar sincronización manual de Tiendanube
"""
import sys
sys.path.insert(0, 'clip_admin_backend')

from app.services.tiendanube_sync_service import start_full_sync

# Cliente Test Clip
CLIENT_ID = '2cb75338-f232-4f8e-88be-bfc0a06b2516'

if __name__ == '__main__':
    print("🚀 Iniciando sincronización de Test Clip...")
    result = start_full_sync(str(CLIENT_ID))

    if result.get('success'):
        print("\n✅ Sincronización completada!")
        print(f"   Duración: {result.get('duration_seconds'):.2f}s")
        print(f"   Stats: {result.get('stats')}")
    else:
        print(f"\n❌ Error: {result.get('error')}")
        print(f"   Stats parciales: {result.get('stats')}")
