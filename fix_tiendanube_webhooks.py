"""
Script para eliminar webhooks incorrectos de Tiendanube y verificar los correctos
"""
import requests
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clip_admin_backend'))

# Datos del cliente Test Clip
CLIENT_ID = "6aaeb2f7-d4ba-4ec3-bde7-8e7225fe3f08"
STORE_ID = "7019043"

print("🔍 Obteniendo datos de integración desde Railway...\n")

from app import create_app
from app.models.tiendanube_integration import TiendanubeIntegration

app = create_app()

with app.app_context():
    integration = TiendanubeIntegration.query.filter_by(client_id=CLIENT_ID).first()

    if not integration:
        print(f"❌ No se encontró integración para client_id {CLIENT_ID}")
        sys.exit(1)

    access_token = integration.get_access_token()
    webhook_ids_db = integration.webhook_ids or {}

    headers = {
        'Authentication': f'bearer {access_token}',
        'User-Agent': 'CLIP Comparador V2'
    }

    # Listar TODOS los webhooks
    print(f"🏪 Store ID: {STORE_ID}")
    print("="*80)

    response = requests.get(
        f'https://api.tiendanube.com/v1/{STORE_ID}/webhooks',
        headers=headers,
        timeout=10,
        verify=False
    )

    if response.status_code != 200:
        print(f"❌ Error obteniendo webhooks: HTTP {response.status_code}")
        sys.exit(1)

    all_webhooks = response.json()

    print(f"\n📊 Total webhooks registrados: {len(all_webhooks)}\n")

    webhooks_to_delete = []
    webhooks_correct = []

    for webhook in all_webhooks:
        webhook_id = webhook.get('id')
        event = webhook.get('event')
        url = webhook.get('url')

        print(f"Webhook ID: {webhook_id}")
        print(f"  Event: {event}")
        print(f"  URL: {url}")

        # Verificar si tiene /api/ en la URL
        if '/api/webhooks/tiendanube/' in url:
            print(f"  ✅ URL CORRECTA\n")
            webhooks_correct.append(webhook_id)
        else:
            print(f"  ❌ URL INCORRECTA - DEBE SER ELIMINADO\n")
            webhooks_to_delete.append({
                'id': webhook_id,
                'event': event,
                'url': url
            })

    print("="*80)
    print(f"\n📊 Resumen:")
    print(f"  ✅ Webhooks correctos: {len(webhooks_correct)}")
    print(f"  ❌ Webhooks incorrectos: {len(webhooks_to_delete)}")

    if webhooks_to_delete:
        print(f"\n🗑️  Eliminando {len(webhooks_to_delete)} webhooks incorrectos...\n")

        for webhook in webhooks_to_delete:
            response = requests.delete(
                f'https://api.tiendanube.com/v1/{STORE_ID}/webhooks/{webhook["id"]}',
                headers=headers,
                timeout=10,
                verify=False
            )

            if response.status_code == 200:
                print(f"  ✅ Eliminado webhook {webhook['event']} (ID: {webhook['id']})")
            else:
                print(f"  ❌ Error eliminando webhook {webhook['id']}: HTTP {response.status_code}")

        print(f"\n✅ Limpieza completada. Ahora Tiendanube usará solo webhooks con URLs correctas.")
    else:
        print(f"\n✅ No hay webhooks incorrectos. Todo está bien configurado.")
