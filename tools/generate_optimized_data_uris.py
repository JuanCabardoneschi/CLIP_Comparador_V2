"""
Genera los 6 data URIs optimizados (WebP ~600px, calidad 70)
y los imprime para copiar/pegar manualmente o insertarlos con otro script.
"""
from __future__ import annotations
import base64
from pathlib import Path
from PIL import Image
import io

IMAGE_PATHS = [
    ('CHAQUETA_POP_NEGRA', Path(r'C:\Personal\CHAQUETA_POP_NEGRA.jpg')),
    ('CAMISA_NEW_NEGRA', Path(r'C:\Personal\CAMISA_NEW_NEGRA.jpg')),
    ('DELANTAL_JUMPER_HABANO', Path(r'C:\Personal\DELANTAL_JUMPER_HABANO.jpg')),
    ('GORRA_CUP_NEGRA', Path(r'C:\Personal\GORRA_CUP_NEGRA.jpg')),
    ('AMBO_NEW_GOODY', Path(r'C:\Personal\AMBO_NEW_GOODY.jpg')),
    ('DELANTAL_IPA_JEAN', Path(r'C:\Personal\DELANTAL_IPA_JEAN.jpg')),
]

MAX_WIDTH = 600
QUALITY = 70


def optimize_image(path: Path) -> str:
    img = Image.open(path)
    if img.width > MAX_WIDTH:
        aspect = img.height / img.width
        new_height = int(MAX_WIDTH * aspect)
        img = img.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    if img.mode in ('RGBA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    buf = io.BytesIO()
    try:
        img.save(buf, format='WEBP', quality=QUALITY, method=6)
        mime = 'image/webp'
    except (OSError, KeyError):
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=QUALITY, optimize=True)
        mime = 'image/jpeg'

    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    size_kb = len(buf.getvalue()) / 1024
    print(f"✓ {path.name}: {img.width}×{img.height} → {size_kb:.1f}KB ({mime})")
    return f'data:{mime};base64,{b64}'


def main():
    print("🔧 Generando data URIs optimizados...\n")

    uris = {}
    for name, path in IMAGE_PATHS:
        if not path.exists():
            print(f'❌ No existe: {path}')
            continue
        uris[name] = optimize_image(path)

    print("\n📋 Data URIs generados (copiar en demo-store.html):\n")

    for name, uri in uris.items():
        print(f"<!-- {name} -->")
        print(f'<img src="{uri[:80]}..." alt="{name}" class="product-image">\n')


if __name__ == '__main__':
    main()
