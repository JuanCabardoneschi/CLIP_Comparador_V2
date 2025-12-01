import json

# Cargar base64
with open('base64_images.json', 'r', encoding='utf-8') as f:
    images = json.load(f)

# demo-store.html: productos Goody
demo_html_path = 'clip_admin_backend/app/static/demo-store.html'
with open(demo_html_path, 'r', encoding='utf-8') as f:
    demo_html = f.read()

# Reemplazar URLs por base64 - usar regex simple reemplazando cualquier cloudinary URL con los base64 en orden
import re

# Buscar todas las URLs cloudinary en orden
cloudinary_pattern = r'https://res\.cloudinary\.com/[^"\']+clients_demo_fashion_store_[^"\']+'

# Las imágenes en orden según aparecen en HTML
base64_order = [
    images['GOD-CHQ-002'],  # Chaqueta Negra
    images['GOD-CAM-001'],  # Camisa Blanca
    images['GOD-GOR-001'],  # Boina Calada
    images['GOD-CAR-002'],  # Cardigan Dama
    images['GOD-BUZ-001'],  # Buzo Frizado
    images['GOD-AMB-002'],  # Ambo New Goody
]

def replace_nth_cloudinary(match):
    """Reemplaza cada URL encontrada con el siguiente base64 de la lista"""
    idx = replace_nth_cloudinary.counter
    replace_nth_cloudinary.counter += 1
    if idx < len(base64_order):
        return base64_order[idx]
    return match.group(0)

replace_nth_cloudinary.counter = 0

demo_html = re.sub(cloudinary_pattern, replace_nth_cloudinary, demo_html)

with open(demo_html_path, 'w', encoding='utf-8') as f:
    f.write(demo_html)

print(f"✅ demo-store.html actualizado con 6 imágenes base64")

# eve-store.html: productos Goody
eve_html_path = 'clip_admin_backend/app/static/eve-store.html'
with open(eve_html_path, 'r', encoding='utf-8') as f:
    eve_html = f.read()

replace_nth_cloudinary.counter = 0
eve_html = re.sub(cloudinary_pattern, replace_nth_cloudinary, eve_html)

with open(eve_html_path, 'w', encoding='utf-8') as f:
    f.write(eve_html)

print(f"✅ eve-store.html actualizado con 6 imágenes base64")

# noa-store.html: 2 Noa + 4 Goody
noa_html_path = 'clip_admin_backend/app/static/noa-store.html'
with open(noa_html_path, 'r', encoding='utf-8') as f:
    noa_html = f.read()

# Patrones para Noa Store (2 productos Noa primero, luego 4 Goody)
noa_cloudinary_pattern = r'https://res\.cloudinary\.com/[^"\']+clients_demo_noa_[^"\']+'
goody_cloudinary_pattern = r'https://res\.cloudinary\.com/[^"\']+clients_demo_fashion_store_[^"\']+'

# Primero reemplazar las 2 de Noa
noa_base64_order = [
    images['PKHT-001-S'],    # Colgante Silver Heart
    images['CHKR-STR-002-N'], # Choker Black Star
]

def replace_nth_noa(match):
    idx = replace_nth_noa.counter
    replace_nth_noa.counter += 1
    if idx < len(noa_base64_order):
        return noa_base64_order[idx]
    return match.group(0)

replace_nth_noa.counter = 0
noa_html = re.sub(noa_cloudinary_pattern, replace_nth_noa, noa_html)

# Luego reemplazar las 4 de Goody (reutilizar primeras 4)
goody_base64_for_noa = [
    images['GOD-GOR-001'],  # Boina
    images['GOD-CAR-002'],  # Cardigan
    images['GOD-BUZ-001'],  # Buzo
    images['GOD-AMB-002'],  # Ambo
]

def replace_nth_goody_in_noa(match):
    idx = replace_nth_goody_in_noa.counter
    replace_nth_goody_in_noa.counter += 1
    if idx < len(goody_base64_for_noa):
        return goody_base64_for_noa[idx]
    return match.group(0)

replace_nth_goody_in_noa.counter = 0
noa_html = re.sub(goody_cloudinary_pattern, replace_nth_goody_in_noa, noa_html)

with open(noa_html_path, 'w', encoding='utf-8') as f:
    f.write(noa_html)

print(f"✅ noa-store.html actualizado con 6 imágenes base64 (2 Noa + 4 Goody)")

print("\n🎉 LISTO! Las 3 páginas ahora usan base64 directo desde la BD")
