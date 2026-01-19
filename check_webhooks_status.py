#!/usr/bin/env python
"""Verificar estado de webhooks en WooCommerce"""
import sys
sys.path.insert(0, 'clip_admin_backend')

from app.services.woocommerce_api_client import WooCommerceAPIClient

# Credenciales de Goody (obtenidas de la BD)
api = WooCommerceAPIClient(
    store_url='https://goodyshop.com.ar',
    consumer_key='ck_2d0db5c18b7b5d5b50c7b9d4c4a5e5f5f',
    consumer_secret='cs_2d0db5c18b7b5d5b50c7b9d4c4a5e5f5f',
    api_version='wc/v3'
)

print('\n=== WEBHOOKS REGISTRADOS EN WOOCOMMERCE ===\n')
try:
    webhooks = api.list_webhooks()
    if not webhooks:
        print('❌ No hay webhooks registrados')
    else:
        for webhook in webhooks:
            print(f"ID: {webhook['id']}")
            print(f"  Topic: {webhook['topic']}")
            print(f"  Delivery URL: {webhook.get('delivery_url', 'N/A')}")
            print(f"  Status: {webhook.get('status', 'N/A')}")
            print(f"  Created: {webhook.get('date_created', 'N/A')}")
            print()
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
