"""
Eliminar webhooks viejos desde Tiendanube API usando store_id
"""
import requests
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

from app import create_app
from app.models.tiendanube_integration import TiendanubeIntegration

store_id = "7019043"  # Del log

app = create_app()

with app.app_context():
    # Buscar integración por store_id
    integration = TiendanubeIntegration.query.filter_by(store_id=store_id).first()

    if not integration:
        print(f"❌ No se encontró integración para store_id={store_id}")
        sys.exit(1)

    print(f"✅ Integración encontrada: {integration.id}")
    print(f"   Cliente: {integration.client.name}")
    print()

    # Obtener token
    access_token = integration.get_access_token()

    headers = {
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'CLIP Comparador V2',
        'Content-Type': 'application/json'
    }

    # Listar webhooks
    print("🔍 Listando TODOS los webhooks en Tiendanube...")
    response = requests.get(
        f'https://api.tiendanube.com/v1/{store_id}/webhooks',
        headers=headers,
        timeout=10,
        verify=False
    )

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    webhooks = response.json()
    print(f"📋 Total: {len(webhooks)} webhooks")
    print()

    # Mostrar todos
    old_webhooks = []
    new_webhooks = []

    for wh in webhooks:
        wh_id = wh.get('id')
        url = wh.get('url', '')
        event = wh.get('event')

        print(f"ID: {wh_id}")
        print(f"Event: {event}")
        print(f"URL: {url}")

        if '/api/webhooks/tiendanube/' not in url:
            old_webhooks.append(wh)
            print("❌ VIEJO (sin /api/)")
        else:
            new_webhooks.append(wh)
            print("✅ CORRECTO")
        print()

    if not old_webhooks:
        print("✅ No hay webhooks viejos")
        sys.exit(0)

    print(f"🗑️ Se encontraron {len(old_webhooks)} webhooks VIEJOS")
    print(f"✅ Se mantendrán {len(new_webhooks)} webhooks correctos")
    print()

    # Eliminar
    print("🗑️ Eliminando webhooks viejos...")
    for wh in old_webhooks:
        wh_id = wh['id']
        event = wh['event']

        print(f"   Eliminando: {event} (ID: {wh_id})")

        del_resp = requests.delete(
            f'https://api.tiendanube.com/v1/{store_id}/webhooks/{wh_id}',
            headers=headers,
            timeout=10,
            verify=False
        )

        if del_resp.status_code == 200:
            print(f"   ✅ Eliminado")
        else:
            print(f"   ❌ Error: {del_resp.status_code}")

    print()
    print("🎉 Completado")
