"""
Inserta las 6 imágenes optimizadas (data URI WebP) directamente
en los <div class="product-image-container"> de demo-store.html
"""
from __future__ import annotations
import base64
from pathlib import Path
from PIL import Image
import io
import re

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / 'demo-store.html'
BACKUP_PATH = ROOT / 'demo-store.images_inserted.bak.html'

IMAGE_PATHS = [
    Path(r'C:\Personal\CHAQUETA_POP_NEGRA.jpg'),
    Path(r'C:\Personal\CAMISA_NEW_NEGRA.jpg'),
    Path(r'C:\Personal\DELANTAL_JUMPER_HABANO.jpg'),
    Path(r'C:\Personal\GORRA_CUP_NEGRA.jpg'),
    Path(r'C:\Personal\AMBO_NEW_GOODY.jpg'),
    Path(r'C:\Personal\DELANTAL_IPA_JEAN.jpg'),
]

ALT_TEXTS = [
    'CHAQUETA POP NEGRA',
    'CAMISA NEW NEGRA',
    'DELANTAL PECHERA JUMPER CON SOLAPA COLOR HABANO',
    'GORRA CUP NEGRA',
    'AMBO EN V NEW GOODY',
    'DELANTAL PECHERA IPA JEAN',
]

MAX_WIDTH = 600
QUALITY = 70


def optimize_to_data_uri(path: Path) -> str:
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
    print(f"  OK {path.name}: {img.width}x{img.height} -> {size_kb:.1f}KB ({mime})")
    return f'data:{mime};base64,{b64}'


def main():
    if not HTML_PATH.exists():
        raise SystemExit(f'No se encuentra {HTML_PATH}')

    print("Optimizando imagenes...")

    data_uris = []
    for path in IMAGE_PATHS:
        if not path.exists():
            raise SystemExit(f'No existe: {path}')
        data_uris.append(optimize_to_data_uri(path))

    print("\nInsertando en HTML...")

    html = HTML_PATH.read_text(encoding='utf-8', errors='ignore')
    BACKUP_PATH.write_text(html, encoding='utf-8')

    # Buscar los 6 bloques de product-image-container vacíos y rellenarlos
    # Patrón: <div class="product-image-container">\s*</div>
    pattern = re.compile(r'(<div class="product-image-container">)\s*(</div>)')

    matches = list(pattern.finditer(html))
    if len(matches) < 6:
        print(f"ADVERTENCIA: Solo se encontraron {len(matches)} contenedores vacios, se esperaban 6")

    # Reemplazar desde el último hacia el primero para mantener índices
    for idx in range(min(len(matches), 6) - 1, -1, -1):
        match = matches[idx]
        img_tag = f'<img src="{data_uris[idx]}" alt="{ALT_TEXTS[idx]}" class="product-image">'
        replacement = f'{match.group(1)}\n                        {img_tag}\n                    {match.group(2)}'
        html = html[:match.start()] + replacement + html[match.end():]

    HTML_PATH.write_text(html, encoding='utf-8')

    final_size_kb = HTML_PATH.stat().st_size / 1024
    print(f"\nListo: 6 imagenes embebidas.")
    print(f"Backup: {BACKUP_PATH}")
    print(f"Tamano final HTML: {final_size_kb:.1f}KB")


if __name__ == '__main__':
    main()
