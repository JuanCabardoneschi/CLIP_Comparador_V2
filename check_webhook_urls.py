"""
Script rápido para verificar las URLs de webhooks en Tiendanube
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

import requests
from app import create_app
from app.models.tiendanube_integration import TiendanubeIntegration

def check_webhooks(client_id: str):
    app = create_app()

    with app.app_context():
        integration = TiendanubeIntegration.query.filter_by(client_id=client_id, is_active=True).first()

        if not integration:
            print(f"❌ No se encontró integración activa para client_id {client_id}")
            return

        print(f"\n🏪 Store: {integration.store_name} (ID: {integration.store_id})")
        print(f"{'='*70}")

        access_token = integration.get_access_token()
        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2 (info@clipcomparador.com)'
        }

        webhook_ids = integration.webhook_ids or {}

        for event, webhook_id in sorted(webhook_ids.items()):
            try:
                response = requests.get(
                    f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{webhook_id}',
                    headers=headers,
                    timeout=10
                )

                if response.status_code == 200:
                    webhook = response.json()
                    url = webhook.get('url', 'N/A')
                    print(f"\n✅ {event} (ID: {webhook_id})")
                    print(f"   URL: {url}")

                    # Verificar si es correcta
                    if '/api/webhooks/tiendanube/' in url:
                        print(f"   ✅ URL correcta")
                    else:
                        print(f"   ❌ URL INCORRECTA - debería tener /api/")
                else:
                    print(f"\n❌ {event}: Error {response.status_code}")
            except Exception as e:
                print(f"\n❌ {event}: Error - {e}")

if __name__ == '__main__':
    client_id = '67f2a7df-ed0e-4141-8453-cba894137a76'
    check_webhooks(client_id)
