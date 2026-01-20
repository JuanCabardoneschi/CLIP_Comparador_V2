#!/usr/bin/env python3
"""
Envía un webhook de prueba a /api/webhooks/woocommerce firmado con HMAC-SHA256
Usa el secret configurado en WooCommerce para validar la entrega.
"""

import requests
import hmac
import hashlib
import base64
import json
import time

# Ajusta estos valores según la captura proporcionada
BASE_URL = "https://clipcomparadorv2-production.up.railway.app"
DELIVERY_ENDPOINT = f"{BASE_URL}/api/webhooks/woocommerce"
WEBHOOK_SECRET = "T4Zi8ERAl7ySNIkaG9ErQRjagXpRvD1NT1xRA9yr0S0"  # Exacto según BD/integración

# Payload mínimo de product.updated (estructura similar a WooCommerce)
payload = {
    "id": 999999,
    "name": "Producto Test Webhook",
    "status": "publish",
    "permalink": "https://goodyshop.com.ar/producto/prueba-webhook/",
    "categories": [
        {"id": 86, "name": "Goody", "slug": "goody"},
        {"id": 90, "name": "Chaquetas", "slug": "chaquetas"}
    ],
    "images": [
        {
            "id": 123,
            "src": "https://via.placeholder.com/600x600.jpg",
            "name": "test-image",
        }
    ],
    "_links": {
        "self": [
            {"href": "https://goodyshop.com.ar/wp-json/wc/v3/products/999999"}
        ]
    }
}

# Serializar body tal cual como se envía
body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

# Calcular firma HMAC-SHA256 en base64
signature = base64.b64encode(
    hmac.new(WEBHOOK_SECRET.encode("utf-8"), body_bytes, hashlib.sha256).digest()
).decode("utf-8")

# Headers simulando WooCommerce
headers = {
    "Content-Type": "application/json",
    "X-WC-Webhook-ID": "9999999",
    "X-WC-Webhook-Topic": "product.updated",
    "X-WC-Webhook-Resource": "product",
    "X-WC-Webhook-Event": "updated",
    "X-WC-Webhook-Signature": signature,
    # WooCommerce suele enviar la fuente
    "X-WC-Webhook-Source": "https://goodyshop.com.ar",
    "User-Agent": "WooCommerce/9.x webhook"
}

print("="*80)
print("Enviando webhook firmado a Railway...")
print(f"POST {DELIVERY_ENDPOINT}")
print("="*80)

try:
    resp = requests.post(DELIVERY_ENDPOINT, data=body_bytes, headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
