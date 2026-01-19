#!/usr/bin/env python
"""
Script para registrar webhooks de WooCommerce en Goody manualmente.
Uso: python register_goody_webhooks.py
"""
import sys
import os

# Asegurarse de que estamos en el directorio correcto
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, 'clip_admin_backend'))
os.chdir(os.path.join(base_dir, 'clip_admin_backend'))

from app import create_app
from app.services.woocommerce_sync_service import WooCommerceSyncService
from app.models.client import Client

def main():
    """Registra webhooks para el cliente Goody"""
    app = create_app()

    with app.app_context():
        # ID del cliente Goody
        client_id = '0fb8cf5d-1ae6-40dd-9741-4004110202a8'

        print(f"🔗 Registrando webhooks para cliente Goody ({client_id})...")

        try:
            # Crear servicio de sincronización
            service = WooCommerceSyncService(client_id)

            # URL de delivery (ajusta si es diferente en tu instalación)
            delivery_url = os.environ.get(
                'WEBHOOK_DELIVERY_URL',
                'https://clip-comparador-v2.railway.app'  # Cambiar si es diferente
            )

            print(f"📍 Delivery URL: {delivery_url}")
            print(f"🏪 Store: {service.integration.store_url}")

            # Registrar webhooks
            result = service.register_webhooks(delivery_url)

            if result.get('success'):
                print(f"\n✅ Webhooks registrados exitosamente!")
                print(f"📋 IDs registrados: {result.get('webhook_ids', [])}")
                print(f"🔑 Secret (hash): {result.get('secret_hash')}")
                print(f"\n📌 Topics registrados:")
                print(f"   - product.created")
                print(f"   - product.updated")
                print(f"   - product.deleted")
                print(f"   - product.restored")
                print(f"\n✨ Webhook endpoint: {delivery_url}/api/webhooks/woocommerce")

                return 0
            else:
                print(f"\n❌ Error registrando webhooks: {result.get('error')}")
                return 1

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == '__main__':
    sys.exit(main())
