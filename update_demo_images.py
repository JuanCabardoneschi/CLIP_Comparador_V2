import json

# Cargar base64
with open('base64_images.json', 'r', encoding='utf-8') as f:
    images = json.load(f)

# demo-store.html: productos Goody
demo_html_path = 'clip_admin_backend/app/static/demo-store.html'
with open(demo_html_path, 'r', encoding='utf-8') as f:
    demo_html = f.read()

# Reemplazar URLs por base64
replacements = {
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod1': images['GOD-CHQ-002'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod2': images['GOD-CAM-001'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod3': images['GOD-GOR-001'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod4': images['GOD-CAR-002'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod5': images['GOD-BUZ-001'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod6': images['GOD-AMB-002'],
}

for url, base64 in replacements.items():
    demo_html = demo_html.replace(url, base64)

with open(demo_html_path, 'w', encoding='utf-8') as f:
    f.write(demo_html)

print(f"✅ demo-store.html actualizado con 6 imágenes base64")

# eve-store.html: productos Goody
eve_html_path = 'clip_admin_backend/app/static/eve-store.html'
with open(eve_html_path, 'r', encoding='utf-8') as f:
    eve_html = f.read()

for url, base64 in replacements.items():
    eve_html = eve_html.replace(url, base64)

with open(eve_html_path, 'w', encoding='utf-8') as f:
    f.write(eve_html)

print(f"✅ eve-store.html actualizado con 6 imágenes base64")

# noa-store.html: 2 Noa + 4 Goody
noa_html_path = 'clip_admin_backend/app/static/noa-store.html'
with open(noa_html_path, 'r', encoding='utf-8') as f:
    noa_html = f.read()

noa_replacements = {
    'https://res.cloudinary.com/dxvprqsf8/image/upload/v1/clip_v2/clip_v2/clients_demo_noa_prod1': images['PKHT-001-S'],
    'https://res.cloudinary.com/dxvprqsf8/image/upload/v1/clip_v2/clip_v2/clients_demo_noa_prod2': images['CHKR-STR-002-N'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod3': images['GOD-GOR-001'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod4': images['GOD-CAR-002'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod5': images['GOD-BUZ-001'],
    'https://res.cloudinary.com/dgtsan81n/image/upload/v1/clip_v2/clip_v2/clients_demo_fashion_store_prod6': images['GOD-AMB-002'],
}

for url, base64 in noa_replacements.items():
    noa_html = noa_html.replace(url, base64)

with open(noa_html_path, 'w', encoding='utf-8') as f:
    f.write(noa_html)

print(f"✅ noa-store.html actualizado con 6 imágenes base64 (2 Noa + 4 Goody)")

print("\n🎉 LISTO! Las 3 páginas ahora usan base64 directo desde la BD")
