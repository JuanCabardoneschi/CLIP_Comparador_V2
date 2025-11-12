"""\nScript de auto-optimizacion de recortes (auto-crop) para mejorar discriminacion\nDelantal Completo vs Medio Delantal.\n\nFlujo:\n1. Carga app y modelo CLIP.\n2. Selecciona imagenes de productos cuya categoria contiene 'DELANTAL' y que NO tienen recorte manual.\n3. Calcula score QA baseline (positive vs negative prompts) sobre imagen completa.\n4. Genera un recorte heuristico centrado en torso (para intentar evidenciar pechera / tirantes).\n   - width_pct ~ 70% (entre 0.38 y 0.68 permitido, usamos 0.70 como limite superior centrado)\n   - height_pct ~ 75% (>=70%) desde la parte superior.\n5. Aplica recorte virtual (sin persistir) y recalcula scores QA.\n6. Si improvement >= threshold (baseline_diff < new_diff por delta), persiste recorte en BD,\n   regenera embedding optimizado y marca refined=True (is_crop_manual=False).\n7. Guarda fila CSV con baseline y nuevo resultado (si no mejora, se marca applied_crop=0 y reason).\n8. Al final recalcula centroides de las categorias afectadas si hubo cambios.\n\nUso:\n  python tools/auto_optimize_crops.py --threshold 0.003 --limit 200\n  python tools/auto_optimize_crops.py --threshold 0.002 --dry-run\n\nOpciones:\n  --threshold FLOAT   Delta minimo (new_diff - baseline_diff) para aplicar recorte (default 0.003)\n  --limit INT         Limite maximo de imagenes a procesar (default: sin limite)\n  --dry-run           No persiste recortes ni embeddings, solo calcula y escribe CSV\n  --only-unrefined    Procesa solo imagenes sin refined True\n\nCSV generado en: clip_admin_backend/logs/autocrop_results_<timestamp>.csv\nColumnas: image_id,product_id,category_name,baseline_positive,baseline_negative,baseline_diff,new_positive,new_negative,new_diff,improvement,applied_crop,crop_x,crop_y,crop_w,crop_h,reason\n"""

import os
import sys
import csv
import argparse
import datetime
import time
import requests
from io import BytesIO
from PIL import Image as PILImage

# Ajustar path para importar app
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import db
# Usamos create_app desde wsgi (patrón factory ya existente allí para scripts fuera de app.py)
try:
    from wsgi import create_app  # cuando se ejecuta dentro de clip_admin_backend
except ImportError:
    # Fallback si el path cambió
    from app import create_app  # puede no existir en algunos entornos; se intenta igualmente
from app.models.image import Image
from app.models.product import Product
from app.models.category import Category
from app.blueprints.embeddings import get_clip_model
from transformers import CLIPProcessor, CLIPModel
import torch
import numpy as np

# Prompts reforzados para QA (consistentes con embeddings.py)
FULL_APRON_PROMPT = "Full apron professional kitchen garment front chest coverage"
HALF_APRON_PROMPT = "Half apron waist-down kitchen garment"
# Version extendida (puede aumentar definicion, mantenemos simple para QA batch)
FULL_APRON_PROMPT_EXT = "full bib apron with large chest panel, shoulder straps, covers torso"
HALF_APRON_PROMPT_EXT = "waist apron without bib or chest coverage tied at waist level"

def download_image(url: str) -> PILImage:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return PILImage.open(BytesIO(resp.content)).convert('RGB')

def compute_qa_scores(pil_img: PILImage, model, processor, use_extended=False, half_as_positive: bool = False):
    """Replica logica del endpoint /api/qa-score para obtener similarity a prompts.
    Retorna (positive_score, negative_score)."""
    if use_extended:
        pair = (HALF_APRON_PROMPT_EXT, FULL_APRON_PROMPT_EXT) if half_as_positive else (FULL_APRON_PROMPT_EXT, HALF_APRON_PROMPT_EXT)
    else:
        pair = (HALF_APRON_PROMPT, FULL_APRON_PROMPT) if half_as_positive else (FULL_APRON_PROMPT, HALF_APRON_PROMPT)
    texts = [pair[0], pair[1]]
    inputs = processor(text=texts, images=pil_img, return_tensors="pt", padding=True)
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.no_grad():
        image_features = model.get_image_features(pixel_values=inputs['pixel_values'])
        text_features = model.get_text_features(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'])
    image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
    sims = (image_features @ text_features.T).cpu().numpy()[0]
    return float(sims[0]), float(sims[1])

def propose_crop(w: int, h: int, focus: str = 'upper'):
    """Genera bounding box heurística.
    focus='upper' (delantal completo): ancho 70% centrado, alto 75% desde top.
    focus='lower' (medio delantal):   ancho 65% centrado, alto 70% desde ~30% vertical.
    Devuelve (x,y,w_crop,h_crop)."""
    if focus == 'lower':
        width_pct = 0.65
        height_pct = 0.70
        crop_w = int(w * width_pct)
        crop_h = int(h * height_pct)
        x = int((w - crop_w) / 2)
        y = int(h * 0.30)
    else:
        width_pct = 0.70
        height_pct = 0.75
        crop_w = int(w * width_pct)
        crop_h = int(h * height_pct)
        x = int((w - crop_w) / 2)
        y = 0

    # Validaciones mínimas (alineadas con UI)
    if crop_w < int(w * 0.40):
        crop_w = int(w * 0.40)
        x = int((w - crop_w) / 2)
    if crop_h < int(h * 0.60):
        crop_h = int(h * 0.60)
    # Ajuste si y+alto excede altura
    if y + crop_h > h:
        y = max(0, h - crop_h)
    return x, y, crop_w, crop_h

def apply_pil_crop(pil_img: PILImage, box):
    x, y, w_crop, h_crop = box
    x2 = x + w_crop
    y2 = y + h_crop
    # Sanitizar limites
    x = max(0, min(x, pil_img.width - 1))
    y = max(0, min(y, pil_img.height - 1))
    x2 = max(x + 1, min(x2, pil_img.width))
    y2 = max(y + 1, min(y2, pil_img.height))
    return pil_img.crop((x, y, x2, y2))

def regenerate_embedding(image_obj, model, processor):
    """Genera embedding optimizado reutilizando generate_clip_embedding logic simplificada (imagen + prompts)."""
    from app.blueprints.embeddings import generate_clip_embedding
    embedding, metadata = generate_clip_embedding(image_obj.display_url, image_obj)
    if embedding is not None:
        import json
        image_obj.clip_embedding = json.dumps(embedding)
        image_obj.is_processed = True
        image_obj.updated_at = datetime.datetime.utcnow()
        return True, metadata
    return False, None

def main():
    parser = argparse.ArgumentParser(description="Auto-optimizacion de recortes para delantales")
    parser.add_argument('--threshold', type=float, default=0.003, help='Delta minimo (new_diff - baseline_diff) para aplicar recorte')
    parser.add_argument('--limit', type=int, default=0, help='Limite maximo de imagenes a procesar (0 = sin limite)')
    parser.add_argument('--dry-run', action='store_true', help='No persiste cambios, solo calcula y genera CSV')
    parser.add_argument('--only-unrefined', action='store_true', help='Solo procesa imagenes que no tengan refined=True')
    parser.add_argument('--use-extended-prompts', action='store_true', help='Usar version extendida de prompts QA')
    parser.add_argument('--category-like', type=str, default='%delantal%', help="Filtro ILIKE para nombre de categoría (ej: '%medio delantal%')")
    parser.add_argument('--adaptive', action='store_true', help='Usar umbral adaptativo: baseline_diff absoluto < 0.003 permite threshold/1.5')
    parser.add_argument('--require-positive', action='store_true', help='Exigir que new_diff >= 0 para aplicar recorte (conservador)')
    args = parser.parse_args()

    app = create_app()
    app.app_context().push()

    model, processor = get_clip_model()
    print(f"🔄 Modelo CLIP cargado para auto-crop")

    # Query base: imagenes de productos con categoria que contenga 'DELANTAL'
    query = db.session.query(Image).join(Product, Image.product_id == Product.id)\
        .join(Category, Product.category_id == Category.id)\
        .filter(Category.name.ilike(args.category_like))

    # Excluir las que tienen recorte manual
    query = query.filter((Image.is_crop_manual.is_(False)) | (Image.is_crop_manual.is_(None)))
    if args.only_unrefined:
        query = query.filter((Image.refined.is_(False)) | (Image.refined.is_(None)))

    images = query.order_by(Image.created_at.asc()).all()
    if args.limit > 0:
        images = images[:args.limit]

    if not images:
        print("⚠️ No se encontraron imágenes candidatas para auto-crop")
        return

    ts_str = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    logs_dir = os.path.join(BACKEND_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    csv_path = os.path.join(logs_dir, f'autocrop_results_{ts_str}.csv')

    affected_categories = set()
    rows = []
    applied_count = 0
    processed_count = 0

    print(f"🚀 Procesando {len(images)} imágenes (threshold={args.threshold}, dry_run={args.dry_run})")

    for img in images:
        processed_count += 1
        reason = ''
        applied = 0
        try:
            if not img.cloudinary_url:
                reason = 'no_cloudinary_url'
                rows.append([img.id, img.product_id, 'N/A', '', '', '', '', '', '', '', applied, '', '', '', '', reason])
                continue

            pil_full = download_image(img.cloudinary_url)
            cat_name = img.product.category.name.upper() if (img.product and img.product.category and img.product.category.name) else ''
            is_half = 'MEDIO DELANTAL' in cat_name
            baseline_pos, baseline_neg = compute_qa_scores(pil_full, model, processor, use_extended=args.use_extended_prompts, half_as_positive=is_half)
            baseline_diff = baseline_pos - baseline_neg

            focus = 'lower' if is_half else 'upper'
            crop_box = propose_crop(pil_full.width, pil_full.height, focus=focus)
            pil_cropped = apply_pil_crop(pil_full, crop_box)
            new_pos, new_neg = compute_qa_scores(pil_cropped, model, processor, use_extended=args.use_extended_prompts, half_as_positive=is_half)
            new_diff = new_pos - new_neg
            improvement = new_diff - baseline_diff

            category_name = img.product.category.name if (img.product and img.product.category) else ''

            # Umbral adaptativo opcional: si baseline_diff es muy pequeño o negativo cercano a cero
            effective_threshold = args.threshold
            if args.adaptive and abs(baseline_diff) < 0.003:
                effective_threshold = args.threshold / 1.5  # relajamos un poco

            # Si se requiere que el resultado final sea positivo, verificar
            meets_positive = (not args.require_positive) or (new_diff >= 0)

            if improvement >= effective_threshold and meets_positive:
                reason = f'improved_{improvement:.4f}'
                if not args.dry_run:
                    # Persistir recorte y regenerar embedding
                    img.crop_x, img.crop_y, img.crop_w, img.crop_h = crop_box
                    img.is_crop_manual = False
                    img.refined = True
                    ok, meta = regenerate_embedding(img, model, processor)
                    if ok:
                        affected_categories.add(img.product.category)
                        applied = 1
                        db.session.commit()
                    else:
                        reason = 'embedding_fail'
                else:
                    applied = 1  # contar como potencialmente aplicado en dry-run
            else:
                reason = f'no_improvement_{improvement:.4f}' if meets_positive else f'filtered_positive_{improvement:.4f}'

            rows.append([
                img.id, img.product_id, category_name,
                f'{baseline_pos:.6f}', f'{baseline_neg:.6f}', f'{baseline_diff:.6f}',
                f'{new_pos:.6f}', f'{new_neg:.6f}', f'{new_diff:.6f}',
                f'{improvement:.6f}', applied,
                crop_box[0], crop_box[1], crop_box[2], crop_box[3], reason
            ])
        except Exception as e:
            reason = f'error_{type(e).__name__}'
            rows.append([img.id, img.product_id, '', '', '', '', '', '', '', '', 0, '', '', '', '', reason])
            print(f"❌ Error procesando imagen {img.id}: {e}")
            continue

    # Recalcular centroides si se aplicaron recortes reales
    if affected_categories and not args.dry_run:
        print(f"🔄 Recalculando centroides para {len(affected_categories)} categorías afectadas...")
        for cat in affected_categories:
            try:
                cat.update_centroid_embedding(force_recalculate=False)
            except Exception as ce:
                print(f"⚠️ Error recalculando centroide {cat.name}: {ce}")
        try:
            db.session.commit()
            print("✅ Centroides actualizados")
        except Exception as e:
            print(f"⚠️ Error commit centroides: {e}")
            db.session.rollback()

    # Escribir CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['image_id','product_id','category_name','baseline_positive','baseline_negative','baseline_diff','new_positive','new_negative','new_diff','improvement','applied_crop','crop_x','crop_y','crop_w','crop_h','reason'])
        writer.writerows(rows)

    print(f"📄 CSV generado: {csv_path}")
    print(f"📊 Resumen: total={len(images)} aplicados={sum(r[10] for r in rows)} (dry_run={args.dry_run}) adaptive={args.adaptive} require_positive={args.require_positive}")

if __name__ == '__main__':
    main()
