import requests
from requests.auth import HTTPBasicAuth

STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347f7d8811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

auth = HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)

url = f"{STORE_URL}/wp-json/wc/v3/products/categories?per_page=5"

print(f"Testing: {url}")
print(f"Auth: {CONSUMER_KEY[:10]}... / {CONSUMER_SECRET[:10]}...")
print()

try:
    response = requests.get(url, auth=auth, timeout=10)
    print(f"TEST 1 - Con SSL verification")
    print(f"Status: {response.status_code}")
    print()
    if response.status_code == 200:
        print(f"✅ Autenticación OK")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Exception: {str(e)}")

print("\n" + "="*80)
print("TEST 2 - Sin SSL verification (verify=False)")
try:
    response = requests.get(url, auth=auth, timeout=10, verify=False)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"✅ Autenticación OK")
    else:
        print(f"❌ Error: {response.status_code}")
except Exception as e:
    print(f"❌ Exception: {str(e)}")

print("\n" + "="*80)
print("TEST 3 - Parámetros en URL")
try:
    response = requests.get(f"{STORE_URL}/wp-json/wc/v3/products/categories",
        params={"per_page": 5, "consumer_key": CONSUMER_KEY, "consumer_secret": CONSUMER_SECRET},
        timeout=10, verify=False)
    print(f"Status: {response.status_code}")
except Exception as e:
    print(f"❌ Exception: {str(e)}")
#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth

STORE_URL = "https://goodyshop.com.ar"
CONSUMER_KEY = "ck_f33c84759c035cf972347f7d8811e4afc6411d31"
CONSUMER_SECRET = "cs_622b4487002880cb739a900c8f77c6ae310b9a3b"

auth = HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)

url = f"{STORE_URL}/wp-json/wc/v3/products/categories?per_page=5"

print(f"Testing: {url}")
print(f"Auth: {CONSUMER_KEY[:10]}... / {CONSUMER_SECRET[:10]}...")
print()

try:
    response = requests.get(url, auth=auth, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print()
    if response.status_code == 200:
        print(f"✅ Autenticación OK")
        categories = response.json()
        for cat in categories[:3]:
            print(f"  - {cat['name']} (ID: {cat['id']})")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Exception: {str(e)}")
