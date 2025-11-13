#!/usr/bin/env python3
"""
Script para recalcular atributos de todos los productos de Goody Store
Usa el endpoint /products/<id>/autofill-attributes del admin panel
"""

import requests
import time

# Configuración
ADMIN_URL = "http://127.0.0.1:5000"
CLIENT_NAME = "Goody Store"

def recalculate_all_attributes():
    """Recalcula atributos para todos los productos usando el endpoint del admin"""

    print("🔧 Iniciando recálculo de atributos para Goody Store...\n")

    # 1. Obtener lista de clientes para encontrar Goody Store
    print("📋 Obteniendo clientes...")
    try:
        resp = requests.get(f"{ADMIN_URL}/api/clients/list", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('success'):
            print(f"❌ Error obteniendo clientes: {data.get('error')}")
            return

        # Buscar Goody Store
        goody = None
        for client in data.get('clients', []):
            if client['name'] == CLIENT_NAME:
                goody = client
                break

        if not goody:
            print(f"❌ Cliente '{CLIENT_NAME}' no encontrado")
            return

        print(f"✅ Cliente encontrado: {goody['name']} (ID: {goody['id']})")

    except Exception as e:
        print(f"❌ Error conectando al servidor: {e}")
        print("⚠️  Asegúrate de que el backend esté corriendo en http://127.0.0.1:5000")
        return

    # 2. Obtener productos del cliente (usando endpoint interno)
    # Como no tenemos endpoint público de productos, vamos a usar la UI del admin
    print("\n⚠️  NOTA: Este script requiere acceso directo a la BD.")
    print("   Alternativa: Usa el panel de admin y el botón 'Recalcular Atributos' en cada producto.")
    print("\n   O ejecuta esto desde el backend:")
    print("""

from app import db
from app.models import Client, Product
from app.services.attribute_autofill_service import AttributeAutofillService

# En Flask shell (flask shell) o script con app context:
goody = Client.query.filter_by(name='Goody Store').first()
products = Product.query.filter_by(client_id=goody.id).all()

for product in products:
    if product.images:
        try:
            result = AttributeAutofillService.autofill_product_attributes(product, overwrite=True)
            if result['success']:
                print(f"✅ {product.name}: {result['filled_count']} atributos")
            else:
                print(f"⚠️  {product.name}: {result.get('message')}")
        except Exception as e:
            print(f"❌ {product.name}: {e}")
    """)

if __name__ == "__main__":
    recalculate_all_attributes()
