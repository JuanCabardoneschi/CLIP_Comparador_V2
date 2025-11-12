"""
Script de auditoría y re-embedding de imágenes de baja calidad.

Objetivo:
  - Identificar imágenes potencialmente problemáticas (muy pequeñas, muy livianas, baja resolución efectiva)
  - Regenerar embeddings usando una transformación Cloudinary de mayor resolución (w=800, calidad auto)
  - Actualizar embeddings y marcar is_processed=True
  - Recalcular centroides al finalizar

Uso (PowerShell):
  cd .\tools\maintenance
  python audit_reembed_quality.py --client-id <CLIENT_ID> --min-width 500 --min-bytes 25000 --limit 300

Parámetros:
  --client-id       ID del cliente (requerido)
  --min-width       Ancho mínimo considerado aceptable (default 500)
  --min-bytes       Tamaño mínimo en bytes (default 25000 ~24KB)
  --limit           Máximo de imágenes a reprocesar en este batch (default None = todas las candidatas)
  --dry-run         No modifica nada, solo muestra reporte
  --only-list       Solo lista candidatas, no re-embebe ni recalcula centroides
  --verbose         Muestra logs detallados

Criterios de baja calidad (se marca si CUALQUIERA se cumple):
  (width < min_width) OR (file_size < min_bytes) OR (width * height < 250_000)  # área muy pequeña

Salida:
  Estadísticas finales impresas en consola.
"""
import os
import sys
import json
import argparse
import traceback
import importlib.util
from typing import List, Dict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
APP_DIR = os.path.join(ROOT, 'clip_admin_backend')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from PIL import Image as PILImage
import requests
import numpy as np

# Cargar Flask app
app_py = os.path.join(APP_DIR, 'app.py')
spec = importlib.util.spec_from_file_location('clip_admin_backend_app', app_py)
app_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(app_module)
flask_app = app_module.create_app()

from app import db
from app.models.image import Image
from app.models.category import Category
from app.blueprints.embeddings import get_clip_model

try:
    import cloudinary
    from cloudinary.utils import cloudinary_url
except Exception:
    cloudinary = None  # Seguimos con URL base


def build_high_res_url(image: Image) -> str:
    """Construye una URL de alta resolución para la imagen usando Cloudinary.

    Usa width=800, calidad auto, formato auto. Si no hay public_id se retorna cloudinary_url original.
    """
    if not image.cloudinary_public_id:
        return image.cloudinary_url
    if cloudinary is None:
        # Fallback simple: intentar manipular la URL agregando parámetros (no siempre funciona)
        return image.cloudinary_url
    url, _ = cloudinary_url(
        image.cloudinary_public_id,
        width=800,
        crop='limit',
        quality='auto:best',
        fetch_format='auto'
    )
    return url


def is_low_quality(img: Image, min_width: int, min_bytes: int) -> bool:
    try:
        w = img.width or 0
        h = img.height or 0
        fs = img.file_size or 0
        area = w * h
        if w < min_width:
            return True
        if fs < min_bytes:
            return True
        if area and area < 250_000:  # ~ <500x500 equivalente
            return True
        return False
    except Exception:
        return True  # ante error, reprocesar


def fetch_image(url: str, timeout: int = 25):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return PILImage.open(requests.compat.BytesIO(r.content)).convert('RGB')


def generate_embedding(pil_img: PILImage, model, processor, device):
    import torch
    with torch.no_grad():
        inputs = processor(images=pil_img, return_tensors='pt').to(device)
        image_features = model.get_image_features(**inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        vec = image_features.cpu().numpy().flatten().tolist()
    return vec


def process_batch(client_id: str, min_width: int, min_bytes: int, limit: int, dry_run: bool, only_list: bool, verbose: bool):
    # Buscar imágenes del cliente
    q = Image.query.filter_by(client_id=client_id).order_by(Image.created_at.desc())
    images = q.all()

    candidates = [im for im in images if is_low_quality(im, min_width, min_bytes)]
    if limit:
        candidates = candidates[:limit]

    print(f"Total imágenes cliente: {len(images)}")
    print(f"Candidatas baja calidad: {len(candidates)} (criterios width<{min_width} OR bytes<{min_bytes} OR area<250k)\n")

    if only_list:
        for im in candidates[:50]:  # limitar salida
            print(f" - {im.id} | {im.filename} | {im.width}x{im.height} | {im.file_size} bytes | processed={im.is_processed}")
        if len(candidates) > 50:
            print(f" ... ({len(candidates)-50} más)")
        return {
            'total': len(images),
            'candidates': len(candidates),
            'reembedded': 0,
            'skipped': 0
        }

    if dry_run:
        print("[DRY-RUN] No se regeneran embeddings. Mostrar primeros 30 candidatos:")
        for im in candidates[:30]:
            print(f" * {im.filename} | {im.width}x{im.height} | {im.file_size} bytes")
        return {
            'total': len(images),
            'candidates': len(candidates),
            'reembedded': 0,
            'skipped': len(candidates)
        }

    # Cargar modelo CLIP
    model, processor = get_clip_model()
    device = next(model.parameters()).device

    reembedded = 0
    skipped = 0

    for im in candidates:
        try:
            high_url = build_high_res_url(im)
            pil_img = fetch_image(high_url)
            vec = generate_embedding(pil_img, model, processor, device)
            # Normalizar manual extra
            arr = np.array(vec, dtype=float)
            n = np.linalg.norm(arr)
            if n > 0:
                arr = arr / n
            im.clip_embedding = json.dumps(arr.tolist())
            im.is_processed = True
            # Actualizar width/height si la transformación da mayor tamaño
            if hasattr(pil_img, 'width') and hasattr(pil_img, 'height'):
                im.width = pil_img.width
                im.height = pil_img.height
            reembedded += 1
            if verbose and reembedded <= 10:
                print(f"Re-embebido OK: {im.filename} → {high_url}")
        except Exception as e:
            skipped += 1
            if verbose:
                print(f"⚠️ Error re-embebiendo {im.filename}: {e}")

    db.session.commit()

    # Recalcular centroides (solo categorías hoja)
    cats = Category.query.filter_by(client_id=client_id, is_active=True).all()
    updated_centroids = 0
    for cat in cats:
        if cat.is_leaf:
            try:
                if cat.update_centroid_embedding(force_recalculate=True):
                    updated_centroids += 1
            except Exception:
                pass
    db.session.commit()

    print("\nResumen re-embedding:")
    print(f"  Re-embebidos: {reembedded}")
    print(f"  Skipped/errores: {skipped}")
    print(f"  Centroides recalculados: {updated_centroids}")

    return {
        'total': len(images),
        'candidates': len(candidates),
        'reembedded': reembedded,
        'skipped': skipped,
        'centroids_updated': updated_centroids
    }


def main():
    parser = argparse.ArgumentParser(description="Auditar y re-embed de imágenes de baja calidad")
    parser.add_argument('--client-id', required=True, help='ID del cliente')
    parser.add_argument('--min-width', type=int, default=500)
    parser.add_argument('--min-bytes', type=int, default=25000)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--only-list', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    with flask_app.app_context():
        try:
            stats = process_batch(
                client_id=args.client_id,
                min_width=args.min_width,
                min_bytes=args.min_bytes,
                limit=args.limit,
                dry_run=args.dry_run,
                only_list=args.only_list,
                verbose=args.verbose
            )
            print("\nJSON Stats:")
            print(json.dumps(stats, indent=2))
        except Exception as e:
            print(f"❌ Error general: {e}")
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()
