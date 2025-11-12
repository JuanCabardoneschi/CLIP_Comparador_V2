"""
Blueprint de Diagnóstico
Endpoint simple para debuggear detección de categorías
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import torch
import os
import json
from PIL import Image as PILImage
from io import BytesIO
import base64
import numpy as np

from app import db
from app.models import Category, Client
from app.utils.blip2_embeddings import get_blip2_system
from app.utils.permissions import requires_role
from app.models.image import Image
from app.models.product import Product

diagnostic_bp = Blueprint('diagnostic', __name__, url_prefix='/diagnostic')


@diagnostic_bp.route('/', methods=['GET'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def index():
    """Página de diagnóstico"""
    return render_template('diagnostic/index.html')


@diagnostic_bp.route('/detect', methods=['POST'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def detect_categories():
    """
    Detectar categorías de una imagen subida

    Proceso:
    1. Recibe imagen
    2. Genera embedding con CLIP
    3. Compara con centroides de categorías del cliente
    4. Retorna resultados ordenados por similitud
    """

    try:
        image_obj = None

        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Archivo vacío'}), 400
            try:
                image_obj = PILImage.open(file.stream).convert('RGB')
            except Exception as e:
                return jsonify({'success': False, 'error': f'Error al cargar imagen: {str(e)}'}), 400
        else:
            image_url = request.form.get('image_url') or request.json.get('image_url') if request.is_json else None
            if not image_url:
                return jsonify({'success': False, 'error': 'No se envió imagen ni image_url'}), 400
            try:
                import requests as rq
                resp = rq.get(image_url, timeout=30)
                if resp.status_code != 200:
                    return jsonify({'success': False, 'error': f'Error HTTP descargando imagen: {resp.status_code}'}), 400
                image_obj = PILImage.open(BytesIO(resp.content)).convert('RGB')
            except Exception as e:
                return jsonify({'success': False, 'error': f'Error descargando image_url: {str(e)}'}), 400

        # Flags de modo (opcional)
        multi_label_enabled = request.form.get('multi_label') in ('1', 'true', 'True', 'on')
        debug_enabled = request.form.get('debug') in ('1', 'true', 'True', 'on')

        # 2. Usar image_obj ya cargada
        image = image_obj

        # 3. Obtener cliente actual
        client_id = current_user.client_id
        client = Client.query.get(client_id)

        if not client:
            return jsonify({
                'success': False,
                'error': 'Cliente no encontrado'
            }), 404

        # 4. Preparar modelo/procesador
        blip2 = get_blip2_system()
        device = next(model.parameters()).device

        # 5. Obtener TODAS las categorías con centroides del cliente
        categories = Category.query.filter(
            Category.client_id == client_id,
            Category.centroid_embedding.isnot(None)
        ).all()

        if not categories:
            return jsonify({
                'success': False,
                'error': 'No hay categorías con centroides en este cliente'
            }), 404

        # 6. Precomputar vectores de categoría (visual, textual y enriquecido)
        #    Mejora: ensamble de prompts (sinónimos) para un texto más robusto sin dataset manual
        cat_vectors = []  # [(category, centroid_unit, text_unit, enriched_unit, prompt)]
        for category in categories:
            try:
                centroid_data = np.array(json.loads(category.centroid_embedding), dtype=float)
                if centroid_data.ndim != 1:
                    continue
                c_norm = np.linalg.norm(centroid_data)
                if c_norm == 0:
                    continue
                centroid_unit = centroid_data / c_norm
            except Exception as e:
                print(f"⚠️ Error parseando centroid de {category.name}: {e}")
                continue

            # Embedding textual por categoría (ancla) usando estructura de BD
            try:
                prompt_variants = []
                # 1) Prompt explícito si está configurado
                if category.clip_prompt and category.clip_prompt.strip():
                    prompt_variants.append(category.clip_prompt.strip())

                # 2) Prompt generado base (name_en + visual_features + alt terms)
                base_name = (category.name_en or category.name or "").strip()
                gen_prompt = Category.generate_clip_prompt(
                    base_name,
                    visual_features=category.visual_features,
                    alternative_terms=category.alternative_terms
                )
                if gen_prompt:
                    prompt_variants.append(gen_prompt)

                # 3) Variantes por sinónimos (si existen), en formato simple
                if category.alternative_terms:
                    alts = [t.strip() for t in category.alternative_terms.split(',') if t.strip()]
                    for alt in alts[:3]:
                        prompt_variants.append(f"a photo of {alt}")

                # 4) Fallback mínimo
                if not prompt_variants:
                    prompt_variants = [f"a product photo of {base_name or category.name}"]

                # Generar embedding de texto promedio (ensamble)
                with torch.no_grad():
                    text_inputs = processor(text=prompt_variants, return_tensors="pt").to(device)
                    text_features = model.get_text_features(**text_inputs)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    # Promedio de variantes y normalizar
                    text_mean = text_features.mean(dim=0, keepdim=True)
                    text_mean = text_mean / text_mean.norm(dim=-1, keepdim=True)
                text_unit = text_mean.cpu().numpy().flatten()
                # Guardar el prompt principal usado (primera variante) solo para debug
                prompt = prompt_variants[0]
            except Exception as e:
                print(f"⚠️ Error generando embedding textual para {category.name}: {e}")
                text_unit = None

            if text_unit is not None:
                alpha, beta = 0.7, 0.3
                enriched = alpha * centroid_unit + beta * text_unit
                e_norm = np.linalg.norm(enriched)
                enriched_unit = enriched / e_norm if e_norm > 0 else centroid_unit
            else:
                enriched_unit = centroid_unit

            cat_vectors.append((category, centroid_unit, text_unit, enriched_unit, prompt))

        # 7. Usar imagen completa (sin crop) para estabilidad y claridad
        best_crop_name = "full"
        best_score = 0.0
        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt").to(device)
            image_features = model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            image_vec = image_features.cpu().numpy().flatten()

        # 7b. Heurística de delantal: bib (completo) vs waist (medio)
        apron_hint = None
        try:
            apron_prompts = [
                "a photo of a bib apron with neck strap and chest coverage",
                "a photo of a waist apron without bib, tied at the waist"
            ]
            with torch.no_grad():
                t_inputs = processor(text=apron_prompts, return_tensors="pt").to(device)
                t_feat = model.get_text_features(**t_inputs)
                t_feat = t_feat / t_feat.norm(dim=-1, keepdim=True)
            v = image_vec
            s_bib = float(np.dot(v, t_feat[0].cpu().numpy().flatten()))
            s_waist = float(np.dot(v, t_feat[1].cpu().numpy().flatten()))
            apron_hint = {
                'bib_score': s_bib,
                'waist_score': s_waist,
                'suggestion': 'Delantal Completo' if s_bib >= s_waist else 'Medio Delantal',
                'confidence_gap': abs(s_bib - s_waist)
            }
        except Exception:
            apron_hint = None

        # 8. Calcular similitudes y probabilidades de texto (zero-shot)
        #    Hiperparámetros para separación más marcada
        temperature = 0.45  # <1.0 endurece el softmax
        weight_text = 0.95
        weight_enriched = 0.05
        preliminary = []
        # Escala de CLIP para logits (≈ e^{logit_scale})
        try:
            logit_scale = float(torch.clamp(model.logit_scale, max=4.6052).exp().detach().cpu().numpy())
        except Exception:
            logit_scale = 100.0

        sims_text = []
        for _, _, text_unit, _, _ in cat_vectors:
            sims_text.append(float(np.dot(image_vec, text_unit)) if text_unit is not None else -1.0)
        logits = torch.tensor(sims_text) * logit_scale
        # Softmax con temperatura para mayor separación
        probs = torch.softmax(logits / max(1e-6, temperature), dim=0).cpu().numpy().tolist()

        for idx, (category, centroid_unit, text_unit, enriched_unit, prompt) in enumerate(cat_vectors):
            sim_raw = float(np.dot(image_vec, centroid_unit))
            sim_enriched = float(np.dot(image_vec, enriched_unit))
            preliminary.append({
                'category': category,
                'centroid_unit': centroid_unit,
                'text_unit': text_unit,
                'enriched_unit': enriched_unit,
                'prompt': prompt,
                'sim_raw': sim_raw,
                'sim_enriched': sim_enriched,
                'sim_text': sims_text[idx],
                'prob_text': probs[idx]
            })

        # 9. Construir resultados ajustados (categorías sin agrupar)
        results = []
        for item in preliminary:
            cat = item['category']
            sim_enr = item['sim_enriched']
            sim_raw = item['sim_raw']
            # Score final: priorizar probabilidad de texto (clasificación), con pequeño aporte de similitud enriquecida
            adjusted = weight_text * item['prob_text'] + weight_enriched * max(0.0, (sim_enr + 1) / 2)

            # Modo multi-label (experimental): score independiente sin softmax
            # Normalizamos cosenos a [0,1] y combinamos enriquecido + texto crudo
            sim_enr_01 = max(0.0, min(1.0, (sim_enr + 1.0) / 2.0))
            sim_text_01 = max(0.0, min(1.0, (item['sim_text'] + 1.0) / 2.0)) if item['text_unit'] is not None else 0.0
            score_ml = 0.5 * sim_enr_01 + 0.5 * sim_text_01

            # Registrar
            results.append({
                'category_id': str(cat.id),
                'category_name': cat.name,
                'parent_name': cat.parent.name if cat.parent else None,
                'similarity': round(adjusted, 4),  # confianza final
                'similarity_text_prob': round(item['prob_text'], 4),
                'similarity_text': round(item['sim_text'], 4),
                'similarity_enriched': round(sim_enr, 4),
                'similarity_raw': round(sim_raw, 4),
                'multi_label_score': round(score_ml, 4),
                'threshold': cat.confidence_threshold,
                'image_count': cat.centroid_image_count or 0,
                'passes_threshold': adjusted >= cat.confidence_threshold,
                'centroid_updated': cat.centroid_updated_at.strftime('%Y-%m-%d %H:%M') if cat.centroid_updated_at else None,
                'prompt_used': item['prompt'],
                'selected_crop': best_crop_name,
                'best_crop_top_score': round(best_score, 4)
            })

        # Ajuste leve guiado por heuristic apron_hint para delantal medio vs completo
        # No agrega listas fijas: usa keywords genéricas de variante.
        try:
            if apron_hint and results:
                gap = float(apron_hint.get('confidence_gap', 0.0) or 0.0)
                suggestion = (apron_hint.get('suggestion') or '').upper()
                if gap >= 0.06 and ('DELANTAL' in ''.join([r['category_name'].upper() for r in results]) or 'APRON' in ''.join([r['category_name'].upper() for r in results])):
                    boost = 0.06
                    penal = 0.04
                    for r in results:
                        name_u = (r.get('category_name') or '').upper()
                        is_apron = ('DELANTAL' in name_u) or ('APRON' in name_u)
                        if not is_apron:
                            continue
                        is_waist_like = any(k in name_u for k in ['MEDIO', 'WAIST'])
                        is_bib_like = any(k in name_u for k in ['COMPLETO', 'BIB'])
                        score_ml = float(r.get('multi_label_score', 0.0))
                        if 'MEDIO' in suggestion or 'WAIST' in suggestion:
                            if is_waist_like:
                                score_ml = min(1.0, score_ml + boost)
                            elif is_bib_like:
                                score_ml = max(0.0, score_ml - penal)
                        elif 'COMPLETO' in suggestion or 'BIB' in suggestion:
                            if is_bib_like:
                                score_ml = min(1.0, score_ml + boost)
                            elif is_waist_like:
                                score_ml = max(0.0, score_ml - penal)
                        r['multi_label_score'] = round(score_ml, 4)
        except Exception:
            pass

    # 10. Ordenar y aplicar fallback si nadie pasa threshold (sin agrupar)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        passing_categories = [r for r in results if r['passes_threshold']]
        fallback_used = False
        fallback_categories = []
        if not passing_categories and results:
            # Threshold adaptativo: top similarity - margen
            top_sim = results[0]['similarity']
            adaptive_th = max(0.60, top_sim - 0.08)
            fallback_categories = [r for r in results if r['similarity'] >= adaptive_th][:3]
            fallback_used = True

        # 10b. Evaluación multi-label (independiente)
        # Threshold ML por categoría: usamos el confidence_threshold de cada categoría
        # (calibrado) en escala [0,1]. Si faltara, usamos 0.35 como valor por defecto.
        ml_threshold_default = 0.35
        passing_categories_ml = []
        top5_ml = []
        if results:
            results_ml_sorted = sorted(results, key=lambda x: x['multi_label_score'], reverse=True)
            top5_ml = results_ml_sorted[:5]
            if multi_label_enabled:
                for r in results_ml_sorted:
                    per_cat_th = r.get('threshold', ml_threshold_default) or ml_threshold_default
                    if r['multi_label_score'] >= per_cat_th:
                        item = {**r, 'passes_multi_label': True, 'multi_label_threshold': per_cat_th}
                        passing_categories_ml.append(item)
                passing_categories_ml = passing_categories_ml[:6]

                # Resolución de familias exclusivas usando configuración dinámica
                try:
                    from app.models.category import Category as _CatModel
                    passing_categories_ml = _CatModel.resolve_exclusive_families(client_id, passing_categories_ml)
                except Exception:
                    pass

                # Regla anti-falsos positivos para delantales cuando upperwear es fuerte
                try:
                    def _is_apron(name: str) -> bool:
                        return 'DELANTAL' in (name or '').upper()

                    def _is_upperwear(name: str) -> bool:
                        n = (name or '').upper()
                        from app.models.category import Category as _CatModel
                        fam_cfg = _CatModel.get_family_config(client_id)
                        upper_list = fam_cfg.get('UPPERWEAR_CORE', [])
                        return any(k in n for k in upper_list)

                    if passing_categories_ml:
                        max_upper = 0.0
                        for it in passing_categories_ml:
                            if _is_upperwear(it['category_name']):
                                max_upper = max(max_upper, float(it.get('multi_label_score', 0.0)))

                        if max_upper >= 0.70:
                            # Filtrar delantales con score bajo si hay upperwear fuerte
                            filtered_ml = []
                            for it in passing_categories_ml:
                                if _is_apron(it['category_name']):
                                    apron_score = float(it.get('multi_label_score', 0.0))
                                    # Suprimir si es claramente más débil que upperwear
                                    if apron_score < 0.58:
                                        continue
                                filtered_ml.append(it)
                            passing_categories_ml = filtered_ml
                except Exception:
                    pass

        # 10c. Productos más similares del catálogo por CATEGORÍA detectada
        #     Requisito: mostrar solo productos de las categorías identificadas en la imagen
        similar_products = []  # compat (global top-N, ya no prioridad)
        similar_products_by_category = []
        try:
            # Elegimos el conjunto de categorías finales a usar para similares
            # Siempre priorizar multi‑label si hay resultados, sin depender del checkbox de UI
            if passing_categories_ml:
                final_cats = [{'id': c['category_id'], 'name': c['category_name']} for c in passing_categories_ml]
            elif passing_categories:
                final_cats = [{'id': c['category_id'], 'name': c['category_name']} for c in passing_categories]
            else:
                # Si nadie pasa, usar fallback (top cercanos) como sugerencias
                final_cats = [{'id': c['category_id'], 'name': c['category_name']} for c in fallback_categories]

            # Para cada categoría, buscar imágenes procesadas de esa categoría y rankear por similitud
            for fc in final_cats:
                cat_id = fc['id']
                cat_name = fc['name']
                # limitar universo a evitar costo alto
                images_q = (
                    db.session.query(Image)
                    .join(Product, Image.product_id == Product.id)
                    .filter(
                        Image.client_id == client_id,
                        Image.is_processed == True,
                        Product.category_id == cat_id
                    )
                    .order_by(Image.created_at.desc())
                    .limit(1200)
                    .all()
                )

                sims = []
                for im in images_q:
                    vec = im.embedding_vector
                    if not vec:
                        continue
                    arr = np.array(vec, dtype=float)
                    n = np.linalg.norm(arr)
                    if n == 0:
                        continue
                    arr = arr / n
                    sim = float(np.dot(image_vec, arr))
                    sims.append((sim, im))

                sims.sort(key=lambda x: x[0], reverse=True)
                items = []
                for sim, im in sims[:6]:
                    items.append({
                        'image_id': im.id,
                        'product_id': im.product_id,
                        'product_name': (im.product.name if getattr(im, 'product', None) else None),
                        'image_url': im.display_url,
                        'similarity': float(round(max(-1.0, min(1.0, sim)), 4))
                    })

                similar_products_by_category.append({
                    'category_id': cat_id,
                    'category_name': cat_name,
                    'items': items
                })

            # Compatibilidad: si no hay categorías o items, mantener top-N global como antes
            if not any(g['items'] for g in similar_products_by_category):
                images_q = Image.query.filter_by(client_id=client_id, is_processed=True).order_by(Image.created_at.desc()).limit(1500).all()
                sims = []
                for im in images_q:
                    vec = im.embedding_vector
                    if not vec:
                        continue
                    arr = np.array(vec, dtype=float)
                    n = np.linalg.norm(arr)
                    if n == 0:
                        continue
                    arr = arr / n
                    sim = float(np.dot(image_vec, arr))
                    sims.append((sim, im))

                sims.sort(key=lambda x: x[0], reverse=True)
                for sim, im in sims[:5]:
                    similar_products.append({
                        'image_id': im.id,
                        'product_id': im.product_id,
                        'product_name': (im.product.name if getattr(im, 'product', None) else None),
                        'image_url': im.display_url,
                        'similarity': float(round(max(-1.0, min(1.0, sim)), 4))
                    })
        except Exception as _e:
            similar_products_by_category = []

    # 11. Retornar resultados (categorías separadas)
        # 11. Construir explicación breve (modo humano)
        explanation = None
        try:
            # Elegir fuente principal: priorizar multi‑label si hay resultados (independientemente del checkbox)
            picked = []
            if passing_categories_ml:
                picked = [p['category_name'] for p in passing_categories_ml]
            elif passing_categories:
                picked = [p['category_name'] for p in passing_categories]
            else:
                picked = [r['category_name'] for r in (results[:2] if results else [])]

            # Regla especial para delantal completo/medio usando apron_hint
            if apron_hint:
                # Si alguna variante de delantal está en picked, reemplazar por sugerencia
                if any('DELANTAL' in (n.upper()) for n in picked):
                    sug = apron_hint['suggestion']
                    picked = [n for n in picked if 'DELANTAL' not in n.upper()]
                    picked.insert(0, sug)

            # Explicación corta
            if picked:
                explanation = {
                    'what_i_see': picked,
                    'apron_disambiguation': apron_hint,
                }
        except Exception:
            explanation = None

        # Lista mínima de categorías detectadas (simple_categories)
        simple_categories = []
        try:
            if passing_categories_ml:
                for p in passing_categories_ml:
                    simple_categories.append({
                        'category_id': p['category_id'],
                        'category_name': p['category_name'],
                        'score': p['multi_label_score'],
                        'threshold': p.get('multi_label_threshold', p.get('threshold'))
                    })
            elif passing_categories:
                for p in passing_categories:
                    simple_categories.append({
                        'category_id': p['category_id'],
                        'category_name': p['category_name'],
                        'score': p['similarity'],
                        'threshold': p.get('threshold')
                    })
            else:
                # Usar hasta 2 sugerencias del fallback
                for p in fallback_categories[:2]:
                    simple_categories.append({
                        'category_id': p['category_id'],
                        'category_name': p['category_name'],
                        'score': p['similarity'],
                        'threshold': p.get('threshold')
                    })
        except Exception:
            simple_categories = []

        return jsonify({
            'success': True,
            'client_name': client.name,
            'total_categories': len(results),
            'categories_passing_threshold': len(passing_categories),
            'top_5_results': results[:5],
            'all_results': results,
            'passing_categories': (passing_categories[:3] if passing_categories else fallback_categories),
            'fallback_used': fallback_used,
            'adaptive_threshold': adaptive_th if fallback_used else None,
            # Multi-label experimental
            'multi_label_enabled': multi_label_enabled,
            # Threshold ML ahora es por categoría; mantenemos el campo para compatibilidad
            # pero marcamos modo dinámico.
            'multi_label_threshold': None,
            'multi_label_threshold_mode': 'per_category',
            'top_5_results_multi_label': top5_ml,
            'passing_categories_multi_label': passing_categories_ml,
            'exclusive_families_applied': True,
            'similar_products': similar_products,
            'similar_products_by_category': similar_products_by_category,
            'explanation': explanation,
            'simple_categories': simple_categories,
            # Debug
            'debug': debug_enabled
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error procesando imagen: {str(e)}'
        }), 500


@diagnostic_bp.route('/categories', methods=['GET'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def list_categories():
    """Listar todas las categorías del cliente con sus estadísticas"""

    try:
        client_id = current_user.client_id

        categories = Category.query.filter(
            Category.client_id == client_id,
            Category.centroid_embedding.isnot(None)
        ).all()

        results = []
        for cat in categories:
            # Contar imágenes con embeddings de esta categoría
            image_count = 0
            for product in cat.products:
                for image in product.images:
                    if image.clip_embedding and image.is_processed:
                        image_count += 1

            results.append({
                'id': str(cat.id),
                'name': cat.name,
                'parent': cat.parent.name if cat.parent else None,
                'threshold': cat.confidence_threshold,
                'image_count': image_count,
                'centroid_updated': cat.centroid_updated_at.strftime('%Y-%m-%d %H:%M') if cat.centroid_updated_at else None
            })

        # Ordenar por cantidad de imágenes
        results.sort(key=lambda x: x['image_count'], reverse=True)

        return jsonify({
            'success': True,
            'total_categories': len(results),
            'categories': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
