"""
Optimiza las 6 imágenes destacadas de GOODY a formato liviano (~10-30KB cada una):
- Redimensiona a ancho máximo 600px conservando aspect ratio
- Convierte a WebP (o JPEG si WebP no disponible) con calidad 70
- Genera data URIs base64 optimizados
- Reemplaza los marcadores [[DATA_URI_FEATURED_1..6]] en demo-store.html

Uso:
  python tools/optimize_and_embed_featured_images.py

Requisitos: Pillow (pip install Pillow)
"""
from __future__ import annotations
import base64
from pathlib import Path
from PIL import Image
import io

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / 'demo-store.html'
BACKUP_PATH = ROOT / 'demo-store.optimized.bak.html'

# Rutas de las 6 imágenes originales
IMAGE_PATHS = [
    Path(r'C:\Personal\CHAQUETA_POP_NEGRA.jpg'),
    Path(r'C:\Personal\CAMISA_NEW_NEGRA.jpg'),
    Path(r'C:\Personal\DELANTAL_JUMPER_HABANO.jpg'),
    Path(r'C:\Personal\GORRA_CUP_NEGRA.jpg'),
    Path(r'C:\Personal\AMBO_NEW_GOODY.jpg'),
    Path(r'C:\Personal\DELANTAL_IPA_JEAN.jpg'),
]

MARKERS = [
    '[[DATA_URI_FEATURED_1]]',
    '[[DATA_URI_FEATURED_2]]',
    '[[DATA_URI_FEATURED_3]]',
    '[[DATA_URI_FEATURED_4]]',
    '[[DATA_URI_FEATURED_5]]',
    '[[DATA_URI_FEATURED_6]]',
]

MAX_WIDTH = 600
QUALITY = 70


def optimize_image(path: Path) -> str:
    """
    Optimiza imagen y retorna data URI base64
    - Redimensiona a MAX_WIDTH px de ancho
    - Convierte a WebP si está disponible, sino JPEG
    - Retorna data:image/webp;base64,... o data:image/jpeg;base64,...
    """
    img = Image.open(path)

    # Redimensionar conservando aspect ratio
    if img.width > MAX_WIDTH:
        aspect = img.height / img.width
        new_height = int(MAX_WIDTH * aspect)
        img = img.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    # Convertir a RGB si es RGBA o P (para JPEG/WebP)
    if img.mode in ('RGBA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Intentar WebP primero
    buf = io.BytesIO()
    try:
        img.save(buf, format='WEBP', quality=QUALITY, method=6)
        mime = 'image/webp'
    except (OSError, KeyError):
        # Fallback a JPEG
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=QUALITY, optimize=True)
        mime = 'image/jpeg'

    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    size_kb = len(buf.getvalue()) / 1024

    print(f"  ✓ {path.name}: {img.width}×{img.height} → {size_kb:.1f}KB ({mime})")
    return f'data:{mime};base64,{b64}'


def main():
    if not HTML_PATH.exists():
        raise SystemExit(f'❌ No se encuentra {HTML_PATH}')

    print("🔧 Optimizando imágenes destacadas...\n")

    data_uris = []
    for idx, path in enumerate(IMAGE_PATHS, start=1):
        if not path.exists():
            raise SystemExit(f'❌ No existe imagen {idx}: {path}')
        data_uri = optimize_image(path)
        data_uris.append(data_uri)

    print(f"\n📝 Reemplazando marcadores en {HTML_PATH.name}...")

    html = HTML_PATH.read_text(encoding='utf-8', errors='ignore')

    # Backup
    BACKUP_PATH.write_text(html, encoding='utf-8')

    # Reemplazar marcadores
    changes = 0
    for marker, data_uri in zip(MARKERS, data_uris):
        if marker in html:
            html = html.replace(marker, data_uri)
            changes += 1
        else:
            print(f"⚠️  Marcador {marker} no encontrado (¿ya reemplazado?)")

    # Escribir
    HTML_PATH.write_text(html, encoding='utf-8')

    print(f"\n✅ Listo: {changes} imágenes embebidas.")
    print(f"   Backup: {BACKUP_PATH}")
    print(f"   Tamaño final HTML: {HTML_PATH.stat().st_size / 1024:.1f}KB")


if __name__ == '__main__':
    main()
