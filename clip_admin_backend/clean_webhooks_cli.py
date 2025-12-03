"""
Script CLI para limpiar webhooks duplicados de Tiendanube
Ejecutar desde el directorio clip_admin_backend
"""
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env.local')

# Importar la app
from app import create_app
from app.models.tiendanube_integration import TiendanubeIntegration
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_webhooks(client_name="Test Clip"):
    """Limpia webhooks duplicados para un cliente"""

    app = create_app()

    with app.app_context():
        # Buscar integración
        integration = TiendanubeIntegration.query.join(
            TiendanubeIntegration.client
        ).filter_by(name=client_name).first()

        if not integration:
            print(f"❌ No se encontró integración para '{client_name}'")
            return False

        print(f"✅ Integración encontrada: {integration.id}")
        print(f"   Store ID: {integration.store_id}")
        print(f"   Cliente: {integration.client.name}")
        print()

        # Obtener token desencriptado
        access_token = integration.get_access_token()

        headers = {
            'Authentication': f'bearer {access_token}',
            'User-Agent': 'CLIP Comparador V2',
            'Content-Type': 'application/json'
        }

        # Listar webhooks
        print("🔍 Listando webhooks en Tiendanube...")
        response = requests.get(
            f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks',
            headers=headers,
            timeout=10,
            verify=False
        )

        if response.status_code != 200:
            print(f"❌ Error listando webhooks: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

        all_webhooks = response.json()
        print(f"📋 Total de webhooks: {len(all_webhooks)}")
        print()

        # Separar webhooks
        old_webhooks = []
        new_webhooks = []

        for wh in all_webhooks:
            wh_id = wh.get('id')
            url = wh.get('url', '')
            event = wh.get('event')

            print(f"   ID: {wh_id}")
            print(f"   Event: {event}")
            print(f"   URL: {url}")

            if '/api/webhooks/tiendanube/' not in url:
                old_webhooks.append(wh)
                print(f"   ❌ INCORRECTO (sin /api/)")
            else:
                new_webhooks.append(wh)
                print(f"   ✅ CORRECTO")
            print()

        if not old_webhooks:
            print("✅ No hay webhooks incorrectos para eliminar")
            return True

        print(f"🗑️ Webhooks incorrectos encontrados: {len(old_webhooks)}")
        print(f"✅ Webhooks correctos a mantener: {len(new_webhooks)}")
        print()

        # Confirmar
        confirm = input("¿Desea eliminar los webhooks incorrectos? (s/n): ")
        if confirm.lower() != 's':
            print("❌ Operación cancelada")
            return False

        print()
        print("🗑️ Eliminando webhooks incorrectos...")

        deleted_count = 0
        for wh in old_webhooks:
            wh_id = wh.get('id')
            event = wh.get('event')

            print(f"   Eliminando: {event} (ID: {wh_id})")

            del_response = requests.delete(
                f'https://api.tiendanube.com/v1/{integration.store_id}/webhooks/{wh_id}',
                headers=headers,
                timeout=10,
                verify=False
            )

            if del_response.status_code == 200:
                print(f"   ✅ Eliminado exitosamente")
                deleted_count += 1
            else:
                print(f"   ❌ Error: {del_response.status_code} - {del_response.text}")

        print()
        print(f"🎉 Limpieza completada:")
        print(f"   ✅ Eliminados: {deleted_count}/{len(old_webhooks)}")
        print(f"   ✅ Mantenidos: {len(new_webhooks)}")

        return True


if __name__ == '__main__':
    client_name = sys.argv[1] if len(sys.argv) > 1 else "Test Clip"
    clean_webhooks(client_name)
