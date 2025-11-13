"""
DEPRECATED: Blueprint de Calibración fue eliminado del sistema.
Este archivo queda como placeholder para evitar errores de importación en entornos antiguos.
"""
raise ImportError("calibration blueprint removed: módulo de calibración deshabilitado")

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime

from app import db
from app.models.training_dataset import TrainingImage, CalibrationRun
from app.models.category import Category
from app.models.client import Client
from app.models.image import Image
from app.services.cloudinary_manager import cloudinary_manager
from app.utils.permissions import requires_role
from app.utils.blip2_embeddings import get_blip2_system
import torch

# Importante: NO definir url_prefix aquí; se establece al registrar el blueprint en app.py
calibration_bp = Blueprint('calibration', __name__)


@calibration_bp.route('/')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def index():
    """Dashboard principal del módulo de calibración"""
    client_id = current_user.client_id

    # Obtener estadísticas del dataset
    stats = TrainingImage.get_statistics(client_id)

    # Últimas imágenes agregadas
    recent_images = TrainingImage.query.filter_by(
        client_id=client_id,
        is_active=True
    ).order_by(TrainingImage.created_at.desc()).limit(10).all()

    # Última calibración ejecutada
    last_calibration = CalibrationRun.query.filter_by(
        client_id=client_id
    ).order_by(CalibrationRun.created_at.desc()).first()

    return render_template('calibration/index.html',
                          stats=stats,
                          recent_images=recent_images,
                          last_calibration=last_calibration)


@calibration_bp.route('/dataset')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def dataset():
    """Gestión completa del dataset de calibración"""
    client_id = current_user.client_id

    # Obtener todas las imágenes del dataset
    images = TrainingImage.get_dataset_for_client(client_id, active_only=False)

    # Enriquecer con nombre de producto (mostrar en UI en lugar del filename)
    try:
        public_ids = [img.cloudinary_public_id for img in images if img.cloudinary_public_id]
        product_names = {}
        if public_ids:
            related = Image.query.filter(
                Image.client_id == client_id,
                Image.cloudinary_public_id.in_(public_ids)
            ).all()
            for im in related:
                try:
                    pname = im.product.name if im.product else None
                except Exception:
                    pname = None
                if pname:
                    product_names[im.cloudinary_public_id] = pname

        # Setear display_name en cada item (pname || filename)
        for it in images:
            it.display_name = product_names.get(it.cloudinary_public_id) or it.filename
    except Exception:
        # Fallback silencioso: usar filename si falla el enriquecimiento
        for it in images:
            it.display_name = it.filename

    # Categorías disponibles del cliente
    categories = Category.query.filter_by(
        client_id=client_id,
        is_active=True
    ).order_by(Category.name).all()

    return render_template('calibration/dataset.html',
                          images=images,
                          categories=categories)


# DEPRECATED: Upload de imágenes externas removido
# Solo usamos referencias a imágenes existentes del catálogo
# No necesitamos consumir storage ni API de Cloudinary


# (def catalog_images ya definido más arriba)


@calibration_bp.route('/image/<image_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def manage_image(image_id):
    """Ver, editar o eliminar imagen del dataset"""
    client_id = current_user.client_id

    image = TrainingImage.query.filter_by(
        id=image_id,
        client_id=client_id
    ).first_or_404()

    if request.method == 'GET':
        # Ver detalles
        return jsonify({
            'success': True,
            'image': image.to_dict()
        })

    elif request.method == 'PUT':
        # Editar etiquetas
        try:
            data = request.get_json()

            if 'expected_categories' in data:
                image.expected_categories = data['expected_categories']

            if 'notes' in data:
                image.notes = data['notes']

            if 'case_type' in data:
                image.case_type = data['case_type']

            if 'is_active' in data:
                image.is_active = data['is_active']

            image.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Imagen actualizada',
                'image': image.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'DELETE':
        # Eliminar (soft delete)
        try:
            image.is_active = False
            image.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Imagen desactivada del dataset'
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500


@calibration_bp.route('/calibrate', methods=['POST'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def calibrate():
    """
    Ejecuta calibración sobre el dataset del cliente
    Calcula métricas y sugiere thresholds óptimos por categoría
    """
    client_id = current_user.client_id

    try:
        # Obtener dataset activo
        images = TrainingImage.get_dataset_for_client(client_id, active_only=True)

        if len(images) < 10:
            return jsonify({
                'success': False,
                'error': 'Se necesitan al menos 10 imágenes en el dataset para calibrar'
            }), 400

        # Importar lógica de calibración
        import requests
        import numpy as np
        from collections import defaultdict

        # Clase auxiliar para métricas
        class CalibrationMetrics:
            def __init__(self):
                self.tp = 0
                self.fp = 0
                self.fn = 0
                self.tn = 0
                self.scores_positive = []
                self.scores_negative = []

            def add_result(self, should_detect, was_detected, score):
                if should_detect and was_detected:
                    self.tp += 1
                    self.scores_positive.append(score)
                elif should_detect and not was_detected:
                    self.fn += 1
                    self.scores_positive.append(score)
                elif not should_detect and was_detected:
                    self.fp += 1
                    self.scores_negative.append(score)
                else:
                    self.tn += 1
                    self.scores_negative.append(score)

            def get_precision(self):
                if self.tp + self.fp == 0:
                    return 0.0
                return self.tp / (self.tp + self.fp)

            def get_recall(self):
                if self.tp + self.fn == 0:
                    return 0.0
                return self.tp / (self.tp + self.fn)

            def get_f1(self):
                p = self.get_precision()
                r = self.get_recall()
                if p + r == 0:
                    return 0.0
                return 2 * (p * r) / (p + r)

            def suggest_threshold(self, method='f1_optimal'):
                if not self.scores_positive:
                    return 0.35

                if method == 'percentile_30':
                    return float(np.percentile(self.scores_positive, 30))
                elif method == 'mean_positive':
                    return float(np.mean(self.scores_positive))
                elif method == 'adaptive_gap':
                    mean_pos = np.mean(self.scores_positive)
                    std_pos = np.std(self.scores_positive) if len(self.scores_positive) > 1 else 0.05
                    return max(0.20, float(mean_pos - std_pos))
                else:  # f1_optimal
                    # Buscar threshold que maximiza F1
                    best_f1 = 0
                    best_threshold = 0.35
                    for threshold in np.linspace(0.1, 0.9, 81):
                        tp = sum(1 for s in self.scores_positive if s >= threshold)
                        fp = sum(1 for s in self.scores_negative if s >= threshold)
                        fn = sum(1 for s in self.scores_positive if s < threshold)

                        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

                        if f1 > best_f1:
                            best_f1 = f1
                            best_threshold = threshold

                    return float(best_threshold)

        # Métricas por categoría
        category_metrics = defaultdict(CalibrationMetrics)
        failed_cases = []

        # URL del endpoint diagnóstico (interno)
        diagnostic_url = request.url_root + 'diagnostic/detect'
        # Reusar la sesión del usuario actual para evitar 302 al login
        session_cookie = request.cookies.get('clip_session')
        auth_headers = {'Cookie': f'clip_session={session_cookie}'} if session_cookie else {}

        print(f"\n🔍 Calibrando sobre {len(images)} imágenes...")

        # Evaluar cada imagen
        for idx, img in enumerate(images, 1):
            expected_categories = set(img.expected_categories)

            print(f"[{idx}/{len(images)}] {img.filename}")

            try:
                # Descargar imagen desde Cloudinary y enviar como archivo al endpoint diagnóstico
                img_resp = requests.get(img.cloudinary_url, timeout=30)
                if img_resp.status_code != 200:
                    print(f"   ❌ No se pudo descargar imagen: HTTP {img_resp.status_code}")
                    continue

                content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
                files = {
                    'image': (img.filename or 'image.jpg', img_resp.content, content_type)
                }
                form_data = {
                    'multi_label': '1'
                }

                response = requests.post(
                    diagnostic_url,
                    headers=auth_headers,
                    data=form_data,
                    files=files,
                    timeout=60
                )

                if response.status_code != 200:
                    print(f"   ❌ Error HTTP: {response.status_code}")
                    continue

                result = response.json()

                if not result.get('success'):
                    print(f"   ❌ Error: {result.get('error')}")
                    continue

                # Extraer resultados
                detected_categories = {}
                all_results = result.get('all_results', [])

                for cat_result in all_results:
                    cat_name = cat_result['category_name']
                    ml_score = cat_result.get('multi_label_score', 0.0)
                    detected_categories[cat_name] = ml_score

                # Categorías detectadas con threshold ML
                passing_ml = result.get('passing_categories_multi_label', [])
                detected_set = set(p['category_name'] for p in passing_ml)

                # Calcular métricas por categoría
                all_categories = set(expected_categories) | set(detected_categories.keys())

                for cat_name in all_categories:
                    should_detect = cat_name in expected_categories
                    was_detected = cat_name in detected_set
                    score = detected_categories.get(cat_name, 0.0)

                    category_metrics[cat_name].add_result(should_detect, was_detected, score)

                # Registrar casos fallidos
                if expected_categories != detected_set:
                    failed_cases.append({
                        'filename': img.filename,
                        'image_url': img.cloudinary_url,
                        'expected': list(expected_categories),
                        'detected': list(detected_set),
                        'false_positives': list(detected_set - expected_categories),
                        'false_negatives': list(expected_categories - detected_set)
                    })

                # Actualizar last_calibration_result en la imagen
                img.last_calibration_result = {
                    'detected': list(detected_set),
                    'scores': detected_categories,
                    'correct': expected_categories == detected_set
                }
                img.last_calibration_date = datetime.utcnow()

            except Exception as e:
                print(f"   ❌ Error procesando: {e}")
                continue

        # Obtener categorías del cliente para thresholds actuales
        categories_db = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        category_thresholds = {cat.name: cat.confidence_threshold or 0.75 for cat in categories_db}

        # Compilar resultados por categoría
        category_results = []
        for cat_name, metrics in category_metrics.items():
            category_results.append({
                'category': cat_name,
                'metrics': {
                    'precision': metrics.get_precision(),
                    'recall': metrics.get_recall(),
                    'f1': metrics.get_f1(),
                    'true_positives': metrics.tp,
                    'false_positives': metrics.fp,
                    'false_negatives': metrics.fn,
                    'true_negatives': metrics.tn
                },
                'current_threshold': category_thresholds.get(cat_name, 0.75),
                'suggested_threshold': metrics.suggest_threshold('f1_optimal')
            })

        # Ordenar por F1 descendente
        category_results.sort(key=lambda x: x['metrics']['f1'], reverse=True)

        # Crear registro de calibración
        # También construir un mapa para thresholds sugeridos esperado por apply_calibration
        threshold_suggestions = {c['category']: c['suggested_threshold'] for c in category_results}
        calibration_run = CalibrationRun(
            client_id=client_id,
            results={
                'timestamp': datetime.utcnow().isoformat(),
                'dataset_size': len(images),
                'categories': category_results,
                'threshold_suggestions': threshold_suggestions,
                'failed_cases': failed_cases[:20],  # Solo primeros 20
                'summary': {
                    'avg_f1': np.mean([c['metrics']['f1'] for c in category_results]) if category_results else 0,
                    'categories_count': len(category_results),
                    'failed_cases_count': len(failed_cases)
                }
            }
        )

        db.session.add(calibration_run)
        db.session.commit()

        print(f"✅ Calibración completada. Run ID: {calibration_run.id}")

        return jsonify({
            'success': True,
            'message': f'Calibración completada sobre {len(images)} imágenes',
            'run_id': str(calibration_run.id),
            'redirect_url': url_for('calibration.calibration_detail', run_id=calibration_run.id)
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error en calibración: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@calibration_bp.route('/calibration/history')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def calibration_history():
    """Historial de calibraciones ejecutadas"""
    client_id = current_user.client_id

    calibrations = CalibrationRun.query.filter_by(
        client_id=client_id
    ).order_by(CalibrationRun.created_at.desc()).all()

    return render_template('calibration/calibration_history.html', calibrations=calibrations)


@calibration_bp.route('/<run_id>')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def calibration_detail(run_id):
    """Ver detalles de una calibración específica"""
    client_id = current_user.client_id

    calibration = CalibrationRun.query.filter_by(
        id=run_id,
        client_id=client_id
    ).first_or_404()

    # Extraer resultados para el template
    results = calibration.results

    return render_template(
        'calibration/calibration_detail.html',
        calibration=calibration,
        results=results
    )


@calibration_bp.route('/<run_id>/apply', methods=['POST'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def apply_calibration(run_id):
    """Aplicar thresholds sugeridos de una calibración"""
    client_id = current_user.client_id

    try:
        run = CalibrationRun.query.filter_by(
            id=run_id,
            client_id=client_id
        ).first_or_404()

        if run.applied:
            return jsonify({
                'success': False,
                'error': 'Esta calibración ya fue aplicada'
            }), 400

        # Extraer thresholds sugeridos
        threshold_suggestions = run.results.get('threshold_suggestions', {})

        if not threshold_suggestions:
            return jsonify({
                'success': False,
                'error': 'No hay thresholds sugeridos en esta calibración'
            }), 400

        # Aplicar a categorías
        updated_count = 0
        for cat_name, suggested_threshold in threshold_suggestions.items():
            category = Category.query.filter_by(
                client_id=client_id,
                name=cat_name
            ).first()

            if category:
                category.confidence_threshold = suggested_threshold
                updated_count += 1

        # Marcar run como aplicado
        run.applied = True
        run.applied_at = datetime.utcnow()
        run.applied_by_user_id = current_user.id

        db.session.commit()

        flash(f'✅ Thresholds aplicados a {updated_count} categorías', 'success')

        return jsonify({
            'success': True,
            'updated_count': updated_count
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@calibration_bp.route('/export')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def export_dataset():
    """Exportar dataset en formato JSON (compatible con script CLI)"""
    client_id = current_user.client_id

    images = TrainingImage.get_dataset_for_client(client_id, active_only=True)

    export_data = {
        'client_id': client_id,
        'export_date': datetime.utcnow().isoformat(),
        'total_images': len(images),
        'images': [
            {
                'filename': img.filename,
                'path': img.cloudinary_url,
                'expected_categories': img.expected_categories,
                'notes': img.notes,
                'case_type': img.case_type
            }
            for img in images
        ]
    }

    return jsonify(export_data)


@calibration_bp.route('/auto-calibrate-weak', methods=['POST'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def auto_calibrate_weak():
    """
    Calibración automática sin dataset (weak labels) usando el catálogo existente.
    - Positivos: imágenes cuyo producto pertenece a la categoría
    - Negativos: el resto
    - Score: mismo esquema multi-label del diagnóstico (enriched/text promedio)

    Guarda los umbrales sugeridos en Category.confidence_threshold.
    """
    client_id = current_user.client_id

    try:
        import numpy as np
        import json as pyjson

        # 1) Obtener categorías con centroides
        categories = Category.query.filter(
            Category.client_id == client_id,
            Category.is_active == True,
            Category.centroid_embedding.isnot(None)
        ).all()

        if not categories:
            return jsonify({'success': False, 'error': 'No hay categorías con centroides'}), 400

        # 2) Modelo/processor para embeddings de texto
        blip2 = get_blip2_system()
        device = next(model.parameters()).device

        # 3) Precomputar vectores por categoría (centroide + texto ensamble + enriquecido)
        cat_vecs = {}  # cat.id -> dict
        for cat in categories:
            try:
                c_vec = np.array(pyjson.loads(cat.centroid_embedding), dtype=float)
                if c_vec.ndim != 1:
                    continue
                c_norm = np.linalg.norm(c_vec)
                if c_norm == 0:
                    continue
                centroid_unit = c_vec / c_norm
            except Exception:
                continue

            # Ensamble de prompts
            prompt_variants = []
            if cat.clip_prompt and cat.clip_prompt.strip():
                prompt_variants.append(cat.clip_prompt.strip())

            base_name = (cat.name_en or cat.name or '').strip()
            gen_prompt = Category.generate_clip_prompt(
                base_name,
                visual_features=cat.visual_features,
                alternative_terms=cat.alternative_terms
            )
            if gen_prompt:
                prompt_variants.append(gen_prompt)
            if cat.alternative_terms:
                alts = [t.strip() for t in cat.alternative_terms.split(',') if t.strip()]
                for alt in alts[:3]:
                    prompt_variants.append(f"a photo of {alt}")
            if not prompt_variants:
                prompt_variants = [f"a product photo of {base_name or cat.name}"]

            try:
                with torch.no_grad():
                    text_inputs = processor(text=prompt_variants, return_tensors='pt').to(device)
                    text_features = model.get_text_features(**text_inputs)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    text_mean = text_features.mean(dim=0, keepdim=True)
                    text_mean = text_mean / text_mean.norm(dim=-1, keepdim=True)
                text_unit = text_mean.cpu().numpy().flatten()
            except Exception:
                text_unit = None

            if text_unit is not None:
                alpha, beta = 0.7, 0.3
                enriched = alpha * centroid_unit + beta * text_unit
                e_norm = np.linalg.norm(enriched)
                enriched_unit = enriched / e_norm if e_norm > 0 else centroid_unit
            else:
                enriched_unit = centroid_unit

            cat_vecs[cat.id] = {
                'cat': cat,
                'centroid_unit': centroid_unit,
                'text_unit': text_unit,
                'enriched_unit': enriched_unit
            }

        if not cat_vecs:
            return jsonify({'success': False, 'error': 'No se pudieron preparar vectores de categorías'}), 400

        # 4) Obtener imágenes procesadas del catálogo (limit para performance)
        #    Usamos embeddings ya calculados en BD para evitar inferencia de imagen.
        images = Image.query.filter_by(client_id=client_id, is_processed=True).order_by(Image.created_at.desc()).all()
        if not images:
            return jsonify({'success': False, 'error': 'No hay imágenes procesadas en el catálogo'}), 400

        MAX_IMAGES = 1500
        images = images[:MAX_IMAGES]

        # 5) Métricas por categoría (débil)
        class Metrics:
            def __init__(self):
                self.tp = 0
                self.fp = 0
                self.fn = 0
                self.tn = 0
                self.pos = []
                self.neg = []

            def add(self, should, score, th=0.5):
                # Guardar para búsqueda de threshold posterior
                if should:
                    self.pos.append(score)
                else:
                    self.neg.append(score)

            def suggest(self):
                # Si no hay positivos, usar 0.35 por defecto
                if not self.pos:
                    return 0.35
                import numpy as _np
                # Opción estable: percentil 35 de positivos
                return float(_np.percentile(self.pos, 35))

        from collections import defaultdict
        metrics = defaultdict(Metrics)

        # 6) Recorrer imágenes y calcular score por categoría
        for img in images:
            try:
                vec = img.embedding_vector
                if not vec:
                    continue
                v = np.array(vec, dtype=float)
                n = np.linalg.norm(v)
                if n == 0:
                    continue
                v = v / n
            except Exception:
                continue

            # Categoría real (débil) del producto
            true_cat_id = getattr(img, 'product', None).category_id if hasattr(img, 'product') and img.product else None

            for cid, data in cat_vecs.items():
                enr = float(np.dot(v, data['enriched_unit']))
                sim_enr_01 = max(0.0, min(1.0, (enr + 1.0) / 2.0))
                if data['text_unit'] is not None:
                    st = float(np.dot(v, data['text_unit']))
                    sim_text_01 = max(0.0, min(1.0, (st + 1.0) / 2.0))
                else:
                    sim_text_01 = sim_enr_01
                score_ml = 0.5 * sim_enr_01 + 0.5 * sim_text_01

                should = (true_cat_id == cid)
                metrics[data['cat'].name].add(should, score_ml)

        # 7) Sugerir thresholds y guardar
        suggestions = {}
        for cid, data in cat_vecs.items():
            cat = data['cat']
            m = metrics.get(cat.name)
            if not m:
                # Si no hay métricas, mantener threshold actual con piso mínimo 0.55
                suggestions[cat.name] = max(0.55, cat.confidence_threshold or 0.55)
            else:
                th = m.suggest()
                # Aplicar piso/techo razonable
                th = float(max(0.45, min(0.90, th)))
                suggestions[cat.name] = th

        # Persistir
        updated = 0
        for cat in categories:
            if cat.name in suggestions:
                cat.confidence_threshold = suggestions[cat.name]
                updated += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'updated_count': updated,
            'method': 'weak_labels_percentile35',
            'max_images_used': len(images),
            'threshold_suggestions': suggestions
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Ruta única para listar imágenes del catálogo
@calibration_bp.route('/catalog-images')
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def catalog_images():
    """Devuelve imágenes del catálogo del cliente para importar al dataset"""
    client_id = current_user.client_id
    q = (request.args.get('q') or '').strip()
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 40))
    except ValueError:
        page, per_page = 1, 40

    query = Image.query.filter_by(client_id=client_id)

    if q:
        like = f"%{q}%"
        query = query.filter((Image.filename.ilike(like)) | (Image.original_filename.ilike(like)))

    query = query.order_by(Image.created_at.desc())

    items = query.limit(per_page).offset((page - 1) * per_page).all()

    return jsonify({
        'success': True,
        'page': page,
        'per_page': per_page,
        'count': len(items),
        'images': [
            {
                'id': img.id,
                'filename': img.filename,
                'product_name': (img.product.name if img.product else None),
                'image_url': img.display_url,
                'thumbnail_url': img.thumbnail_url,
                'product_id': img.product_id,
                'created_at': img.created_at.isoformat() if img.created_at else None
            }
            for img in items
        ]
    })

@calibration_bp.route('/import-from-catalog', methods=['POST'])
@login_required
@requires_role('STORE_ADMIN', 'SUPER_ADMIN')
def import_from_catalog():
    """Crea un TrainingImage a partir de una imagen del catálogo existente"""
    client_id = current_user.client_id
    try:
        data = request.get_json(force=True)
        image_id = data.get('image_id')
        expected_categories = data.get('expected_categories') or []
        notes = (data.get('notes') or '').strip()
        case_type = data.get('case_type') or 'general'

        if not image_id:
            return jsonify({'success': False, 'error': 'Falta image_id'}), 400
        if not expected_categories:
            return jsonify({'success': False, 'error': 'Debe seleccionar al menos una categoría esperada'}), 400

        img = Image.query.filter_by(id=image_id, client_id=client_id).first()
        if not img:
            return jsonify({'success': False, 'error': 'Imagen no encontrada'}), 404

        existing = TrainingImage.query.filter_by(client_id=client_id, cloudinary_url=img.display_url).first()
        if existing:
            existing.expected_categories = expected_categories
            existing.notes = notes
            existing.case_type = case_type
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'image_id': existing.id, 'updated': True})

        training_image = TrainingImage(
            client_id=client_id,
            filename=img.filename,
            cloudinary_public_id=img.cloudinary_public_id,
            cloudinary_url=img.display_url,
            expected_categories=expected_categories,
            notes=notes,
            case_type=case_type,
            created_by_user_id=current_user.id
        )

        db.session.add(training_image)
        db.session.commit()

        return jsonify({'success': True, 'image_id': training_image.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
