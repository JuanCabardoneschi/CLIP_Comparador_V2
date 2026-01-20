#!/usr/bin/env python3
"""
Test diferentes métodos de autenticación con WooCommerce API
"""

import requests
import base64
import warnings

warnings.filterwarnings('ignore')

STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347f7d8811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

api_base = f"{STORE_URL}/wp-json/wc/v3"

print("=" * 80)
print("Testing WooCommerce Authentication Methods")
print("=" * 80)
print()

# TEST 1: URL Parameters (sin SSL verify)
print("TEST 1: URL Parameters (verify=False)")
try:
    url = f"{api_base}/products/categories"
    params = {
        "consumer_key": CONSUMER_KEY,
        "consumer_secret": CONSUMER_SECRET,
        "per_page": 1
    }
    response = requests.get(url, params=params, verify=False)
    print(f"  Status: {response.status_code}")
    if response.status_code != 200:
        print(f"  Response: {response.text[:200]}")
except Exception as e:
    print(f"  Error: {str(e)}")

print()

# TEST 2: Basic Auth Header
print("TEST 2: Basic Auth Header (verify=False)")
try:
    url = f"{api_base}/products/categories"
    auth_str = base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}"}
    response = requests.get(url, headers=headers, verify=False, params={"per_page": 1})
    print(f"  Status: {response.status_code}")
    if response.status_code != 200:
        print(f"  Response: {response.text[:200]}")
except Exception as e:
    print(f"  Error: {str(e)}")

print()

# TEST 3: Bearer Token (long shot)
print("TEST 3: Bearer Token Header (verify=False)")
try:
    url = f"{api_base}/products/categories"
    headers = {"Authorization": f"Bearer {CONSUMER_KEY}"}
    response = requests.get(url, headers=headers, verify=False, params={"per_page": 1})
    print(f"  Status: {response.status_code}")
    if response.status_code != 200:
        print(f"  Response: {response.text[:200]}")
except Exception as e:
    print(f"  Error: {str(e)}")

print()

# TEST 4: Check categories endpoint directly
print("TEST 4: Categories endpoint with URL params (verify=False)")
try:
    url = f"{api_base}/products/categories"
    params = {
        "consumer_key": CONSUMER_KEY,
        "consumer_secret": CONSUMER_SECRET
    }
    response = requests.get(url, params=params, verify=False)
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Categories found: {len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, list) and len(data) > 0:
            print(f"  Sample: {data[0].get('name')} (ID: {data[0].get('id')})")
    else:
        print(f"  Response: {response.text[:200]}")
except Exception as e:
    print(f"  Error: {str(e)}")

print()
print("=" * 80)
