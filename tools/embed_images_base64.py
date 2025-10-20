"""
Convierte 6 imágenes locales en data URIs base64 y reemplaza los marcadores
[[DATA_URI_FEATURED_1..6]] dentro de demo-store.html.

Uso (PowerShell):
  python .\tools\embed_images_base64.py \
    --img1 path\a\CHAQUETA_POP_NEGRA.jpg \
    --img2 path\a\CAMISA_NEW_NEGRA.jpg \
    --img3 path\a\DELANTAL_JUMPER_HABANO.jpg \
    --img4 path\a\GORRA_CUP_NEGRA.jpg \
    --img5 path\a\AMBO_NEW_GOODY.jpg \
    --img6 path\a\DELANTAL_IPA_JEAN.jpg

Deja una copia de respaldo demo-store.bak.html y escribe el HTML final.
"""
from __future__ import annotations
import argparse
import base64
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / 'demo-store.html'
BACKUP_PATH = ROOT / 'demo-store.bak.html'

MARKERS = [
    '[[DATA_URI_FEATURED_1]]',
    '[[DATA_URI_FEATURED_2]]',
    '[[DATA_URI_FEATURED_3]]',
    '[[DATA_URI_FEATURED_4]]',
    '[[DATA_URI_FEATURED_5]]',
    '[[DATA_URI_FEATURED_6]]',
]

def file_to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        # fallback común
        ext = path.suffix.lower()
        if ext in {'.jpg', '.jpeg'}:
            mime = 'image/jpeg'
        elif ext == '.png':
            mime = 'image/png'
        elif ext == '.webp':
            mime = 'image/webp'
        else:
            raise ValueError(f'No se pudo determinar MIME para: {path}')
    b64 = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{b64}'


def main():
    p = argparse.ArgumentParser()
    for i in range(1, 7):
        p.add_argument(f'--img{i}', type=str, required=True)
    args = p.parse_args()

    imgs = [Path(getattr(args, f'img{i}')).expanduser().resolve() for i in range(1, 7)]
    for i, pth in enumerate(imgs, start=1):
        if not pth.exists():
            raise SystemExit(f'❌ No existe img{i}: {pth}')

    # Leer HTML
    html = HTML_PATH.read_text(encoding='utf-8')

    # Reemplazar
    for idx, pth in enumerate(imgs, start=1):
        data_uri = file_to_data_uri(pth)
        marker = MARKERS[idx - 1]
        if marker not in html:
            print(f'⚠️  Marcador {marker} no encontrado (ya reemplazado?).')
        html = html.replace(marker, data_uri)
        print(f'✓ img{idx} embebida ({pth.name})')

    # Backup y escribir
    BACKUP_PATH.write_text(html, encoding='utf-8')
    HTML_PATH.write_text(html, encoding='utf-8')
    print(f'✅ Listo. Se actualizó {HTML_PATH} y se guardó respaldo en {BACKUP_PATH}')


if __name__ == '__main__':
    main()
