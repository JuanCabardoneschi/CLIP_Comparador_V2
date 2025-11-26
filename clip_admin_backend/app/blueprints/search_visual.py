"""
Lógica de Búsqueda Visual separada de api.py

Incluye generación de embeddings de imagen, detección de color y objeto,
similaridad y construcción de resultados.
"""
from __future__ import annotations

import io
import time
import numpy as np
import torch
from flask import jsonify
from sqlalchemy import text

from app import db
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from app.blueprints.embeddings import get_clip_model
from app.utils.system_config import system_config


def process_image_for_search(image_data):
    """Procesar imagen y generar embedding para búsqueda"""
    try:
        import logging
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.getLogger("clip_model").info(f"[REQUEST] Comparación recibida")

        print("🛠 DEBUG: Iniciando procesamiento de imagen")

        # Importar PIL con alias para evitar conflictos
        from PIL import Image as PILImage
        print("🛠 DEBUG: Importaciones exitosas")

        # Convertir bytes a imagen PIL
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"🛠 DEBUG: Imagen PIL creada: {pil_image.size}")

        # Obtener modelo CLIP directamente
        start_clip_time = time.time()
        model, processor = get_clip_model()
        clip_load_time = time.time() - start_clip_time
        print(f"� CLIP MODEL: Obtenido en {clip_load_time:.3f}s")

        # Generar embedding usando solo argumentos necesarios
        print("🛠 DEBUG: Llamando al procesador CLIP...")

        # Llamada simplificada al procesador
        with torch.no_grad():
            inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            print("🛠 DEBUG: Inputs del procesador creados exitosamente")

            # Generar features de imagen
            image_features = model.get_image_features(**inputs)
            print(f"🛠 DEBUG: Image features generadas: {image_features.shape}")

            # Normalizar embedding
            embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Convertir a lista de Python
            embedding_list = embedding.squeeze().cpu().numpy().tolist()

        print(f"✅ DEBUG: Embedding generado exitosamente: {len(embedding_list)} dimensiones")
        return embedding_list, None

    except Exception as e:
        print(f"❌ DEBUG: Error en process_image_for_search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error procesando imagen: {str(e)}"


def calculate_similarity(embedding1, embedding2):
    """Calcular similitud coseno entre embeddings"""
    if isinstance(embedding1, str):
        embedding1 = eval(embedding1)  # Convertir string a lista
    if isinstance(embedding2, str):
        embedding2 = eval(embedding2)

    embedding1 = np.array(embedding1)
    embedding2 = np.array(embedding2)

    # Normalizar
    embedding1 = embedding1 / np.linalg.norm(embedding1)
    embedding2 = embedding2 / np.linalg.norm(embedding2)

    # Similitud coseno
    similarity = np.dot(embedding1, embedding2)
    return float(similarity)


def _generate_query_embedding(image_data, detected_category=None):
    """
    Genera el embedding de la imagen de consulta con enriquecimiento opcional por tags

    Args:
        image_data: Bytes de la imagen
        detected_category: Categoría detectada (opcional, para contexto)

    Returns:
        Tuple: (embedding_enriquecido, error_response, status_code)
    """
    print(f"📷 DEBUG: Procesando imagen de {len(image_data)} bytes")
    query_embedding, error = process_image_for_search(image_data)
    if error:
        print(f"❌ DEBUG: Error en procesamiento: {error}")
        return None, jsonify({
            "error": "processing_failed",
            "message": error
        }), 500

    if query_embedding is None:
        print("❌ DEBUG: query_embedding es None")
        return None, jsonify({
            "error": "processing_failed",
            "message": "No se pudo generar embedding de la imagen"
        }), 500

    print(f"🧠 DEBUG: Embedding generado - dimensiones: {len(query_embedding)}")
    print(f"🧠 DEBUG: Primeros 5 valores: {query_embedding[:5]}")

    # ✨ ENRIQUECIMIENTO CON TAGS INFERIDOS (para búsqueda visual)
    fusion_enabled = system_config.get('search', 'enable_inferred_tags', False)
    if fusion_enabled:
        try:
            from PIL import Image
            from io import BytesIO
            from app.services.attribute_autofill_service import AttributeAutofillService
            # Convertir bytes a PIL Image
            pil_image = Image.open(BytesIO(image_data)).convert('RGB')
            category_context = detected_category.name.lower() if detected_category else "producto"

            # Inferir tags visuales de la imagen subida
            from app.services.attribute_autofill_service import TAG_OPTIONS
            inferred_tags = AttributeAutofillService._classify_tags(
                pil_image,
                TAG_OPTIONS,
                threshold=0.15,
                category_context=category_context
            )

            if inferred_tags and len(inferred_tags) > 0:
                # Tomar top 5 tags más relevantes
                top_tags = inferred_tags[:5]
                tag_names = [tag for tag, _ in top_tags]

                print(f"🎯 VISUAL FUSION: Tags inferidos de imagen: {', '.join([f'{t}({c:.2f})' for t, c in top_tags])}")

                # Generar embeddings de los tags
                model, processor = get_clip_model()
                tag_phrases = [f"a {tag} style {category_context}" for tag in tag_names]

                with torch.no_grad():
                    tag_inputs = processor(text=tag_phrases, return_tensors="pt", padding=True)
                    tag_embeddings = model.get_text_features(**tag_inputs)
                    tag_embeddings = tag_embeddings / tag_embeddings.norm(dim=-1, keepdim=True)
                    tag_mean = tag_embeddings.mean(dim=0)
                    tag_mean = tag_mean / tag_mean.norm()

                    # Fusionar: 80% visual + 20% tags inferidos
                    q = torch.tensor(query_embedding).unsqueeze(0)
                    q = q / q.norm()

                    alpha = 0.8  # Peso del embedding visual original
                    beta = 0.2   # Peso de los tags inferidos

                    fused = alpha * q + beta * tag_mean
                    fused = fused / fused.norm()
                    query_embedding = fused.squeeze().cpu().numpy().tolist()

                    print(f"✨ VISUAL FUSION: Embedding enriquecido (α={alpha} visual + β={beta} tags)")

        except Exception as e:
            print(f"⚠️ VISUAL FUSION skip: {e}")
            # Si falla, continuar con embedding original
            pass

    return query_embedding, None, None


def _find_similar_products(client, query_embedding, threshold):
    """Encuentra productos similares y agrupa por mejor coincidencia"""
    # Buscar imágenes similares en la base de datos
    images = Image.query.filter_by(
        client_id=client.id,
        is_processed=True
    ).filter(Image.clip_embedding.isnot(None)).all()

    print(f"🔍 DEBUG: Encontradas {len(images)} imágenes para comparar")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto
    category_similarities = {}  # Para determinar categoría más probable

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categoría"

            print(f"🔍 DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            # Recopilar estadísticas por categoría
            if category_name not in category_similarities:
                category_similarities[category_name] = []
            category_similarities[category_name].append(similarity)

            if similarity >= threshold:
                product_id = img.product.id

                # Si es la primera imagen de este producto, o si tiene mayor similitud que la anterior
                if product_id not in product_best_match or similarity > product_best_match[product_id]['similarity']:
                    product_best_match[product_id] = {
                        'image': img,
                        'similarity': similarity,
                        'product': img.product,
                        'category': category_name
                    }
                    print(f"✅ DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"❌ Error calculando similitud para imagen {img.id}: {e}")
            continue

    # Determinar categoría más probable basada en mayor similitud promedio
    print(f"\n📊 DEBUG: Análisis por categorías:")
    best_category = None
    best_avg_similarity = 0

    for category, similarities in category_similarities.items():
        avg_sim = sum(similarities) / len(similarities)
        max_sim = max(similarities)
        count = len(similarities)
        print(f"   📂 {category}: {count} productos, promedio: {avg_sim:.4f}, máximo: {max_sim:.4f}")

        if max_sim > best_avg_similarity:  # Usar máximo en lugar de promedio para detectar categoría objetivo
            best_avg_similarity = max_sim
            best_category = category

    print(f"🎯 DEBUG: Categoría más probable: '{best_category}' (similitud máxima: {best_avg_similarity:.4f})")

    # Aplicar boost de categoría: aumentar similitud para productos de la categoría más probable
    if best_category and best_category != "Sin categoría":
        for product_id in product_best_match:
            match_data = product_best_match[product_id]
            if match_data['category'] == best_category:
                # Boost del 15% para productos de la misma categoría
                original_similarity = match_data['similarity']
                boosted_similarity = min(1.0, original_similarity * 1.15)
                match_data['similarity'] = boosted_similarity
                match_data['category_boost'] = True
                print(f"🚀 DEBUG: Boost aplicado a {match_data['product'].name}: {original_similarity:.4f} → {boosted_similarity:.4f}")
            else:
                match_data['category_boost'] = False

    print(f"🎯 DEBUG: Productos únicos encontrados: {len(product_best_match)}")
    return product_best_match


def _find_similar_products_in_category(client, query_embedding, threshold, category_id):
    """
    Encuentra productos similares SOLO dentro de una categoría específica

    Args:
        client: Cliente autenticado
        query_embedding: Embedding de la imagen query
        threshold: Umbral mínimo de similitud
        category_id: ID de la categoría en la que buscar

    Returns:
        dict: Diccionario con los mejores matches por producto
    """
    # Buscar imágenes SOLO de la categoría específica
    images = (Image.query
              .join(Product)
              .filter(
                  Image.client_id == client.id,
                  Image.is_processed == True,
                  Image.clip_embedding.isnot(None),
                  Product.category_id == category_id
              ).all())

    print(f"🔍 DEBUG: Encontradas {len(images)} imágenes en la categoría específica")

    # Calcular similitudes y agrupar por producto
    product_best_match = {}  # Dict para almacenar la mejor imagen de cada producto

    for img in images:
        try:
            similarity = calculate_similarity(query_embedding, img.clip_embedding)
            category_name = img.product.category.name if img.product.category else "Sin categoría"

            print(f"🔍 DEBUG: Similitud con {img.product.name[:30]} ({category_name}): {similarity:.4f}")

            if similarity >= threshold:
                product_id = img.product.id

                # Si es la primera imagen de este producto, o si tiene mayor similitud que la anterior
                if product_id not in product_best_match or similarity > product_best_match[product_id]['similarity']:
                    product_best_match[product_id] = {
                        'image': img,
                        'similarity': similarity,
                        'product': img.product,
                        'category': category_name,
                        'category_filtered': True  # Indicador de que se filtró por categoría
                    }
                    print(f"✅ DEBUG: Mejor imagen para {img.product.name}: {similarity:.4f}")

        except Exception as e:
            print(f"❌ Error calculando similitud para imagen {img.id}: {e}")
            continue

    print(f"🎯 DEBUG: Total productos únicos encontrados en categoría: {len(product_best_match)}")
    return product_best_match


def _apply_category_filter(product_best_match, limit):
    """Aplica filtrado inteligente por categoría si es necesario"""
    # Filtrado inteligente por categoría (solo si hay suficientes productos)
    if len(product_best_match) <= limit * 2:  # Solo filtrar si hay muchos productos
        print(f"🎯 DEBUG: Pocos productos encontrados ({len(product_best_match)}), no se aplica filtro de categoría")
        return product_best_match

    # Obtener las categorías de los productos con mayor similitud
    sorted_products = sorted(product_best_match.items(), key=lambda x: x[1]['similarity'], reverse=True)

    # Tomar las top similitudes para determinar la categoría dominante
    top_count = min(3, len(sorted_products))
    top_categories = {}

    for product_id, match_data in sorted_products[:top_count]:
        category_name = match_data['product'].category.name
        if category_name not in top_categories:
            top_categories[category_name] = []
        top_categories[category_name].append(match_data['similarity'])

    # Determinar la categoría más relevante basada en similitud promedio
    best_category = None
    best_avg_similarity = 0

    for category, similarities in top_categories.items():
        avg_similarity = sum(similarities) / len(similarities)
        print(f"📚 DEBUG: Categoría '{category}': {len(similarities)} productos, similitud promedio: {avg_similarity:.4f}")

        if avg_similarity > best_avg_similarity:
            best_avg_similarity = avg_similarity
            best_category = category

    # Solo aplicar filtro si la categoría dominante es muy clara (>60% similitud promedio)
    if not (best_category and best_avg_similarity > 0.6):
        print(f"🎯 DEBUG: No se aplicó filtro de categoría (similitud promedio: {best_avg_similarity:.4f})")
        return product_best_match

    print(f"🎯 DEBUG: Categoría dominante detectada: '{best_category}' (similitud promedio: {best_avg_similarity:.4f})")

    # Filtrar solo productos de la categoría dominante
    filtered_matches = {}
    for product_id, match_data in product_best_match.items():
        product_category = match_data['product'].category.name

        # Incluir productos de la categoría dominante
        if product_category == best_category:
            filtered_matches[product_id] = match_data
            print(f"✅ DEBUG: Incluido por categoría exacta: {match_data['product'].name} ({product_category})")
        else:
            print(f"❌ DEBUG: Excluido por categoría: {match_data['product'].name} ({product_category} != {best_category})")

    # Solo usar el filtro si queda al menos el mínimo de productos
    if len(filtered_matches) >= limit:
        print(f"🎯 DEBUG: Productos después del filtro de categoría: {len(filtered_matches)}")
        return filtered_matches
    else:
        print("⚠️ DEBUG: El filtro de categoría eliminó demasiados productos, manteniendo los originales")
        return product_best_match


def _build_search_results(product_best_match, limit):
    """Construye la lista final de resultados"""
    results = []

    # 🔍 DEBUG: Verificar contenido del dict recibido
    print(f"🔍 DEBUG _build_search_results: Recibido dict con {len(product_best_match)} productos")
    if product_best_match:
        sample_id = list(product_best_match.keys())[0]
        sample_match = product_best_match[sample_id]
        print(f"🔍 DEBUG _build_search_results: Claves en sample_match: {list(sample_match.keys())}")
        print(f"🔍 DEBUG _build_search_results: Tiene optimizer_scores: {'optimizer_scores' in sample_match}")

    # Intentar obtener configuración de atributos a exponer (si existe la tabla)
    exposed_keys_cache = None  # cache por request
    checked_config = False
    for product_id, best_match in product_best_match.items():
        img = best_match['image']
        product = best_match['product']
        similarity = best_match['similarity']
        category_boost = best_match.get('category_boost', False)
        color_boost = best_match.get('color_boost', False)

        # La primera vez, intentamos cargar la config de atributos visibles por cliente
        if not checked_config:
            try:
                client_id = getattr(product, 'client_id', None)
                if client_id:
                    # Primero verificar si hay ALGUNA configuración para este cliente
                    total_configs = db.session.execute(
                        text(
                            """
                            SELECT COUNT(*) as total
                            FROM product_attribute_config
                            WHERE client_id = :client_id
                            """
                        ),
                        {"client_id": client_id},
                    ).fetchone()

                    # Si no hay ninguna configuración, tratar como "sin config" (None)
                    if total_configs and total_configs[0] == 0:
                        exposed_keys_cache = None
                    else:
                        # Hay configuraciones, obtener las visibles
                        rows = db.session.execute(
                            text(
                                """
                                SELECT key
                                FROM product_attribute_config
                                WHERE client_id = :client_id AND expose_in_search = true
                                """
                            ),
                            {"client_id": client_id},
                        ).fetchall()
                        # Crear conjunto (vacío si todas están ocultas, con elementos si hay visibles)
                        exposed_keys_cache = {r[0] for r in rows}
            except Exception as e:
                # Si no existe la tabla o falla, seguimos sin filtrar (compatible hacia atrás)
                print(f"⚠️ Error consultando product_attribute_config: {e}")
                # CRITICAL: Hacer rollback para que queries posteriores funcionen
                db.session.rollback()
                exposed_keys_cache = None
            finally:
                checked_config = True

        # Obtener la imagen primaria del producto en lugar de la que hizo match
        primary_image = None
        try:
            # Buscar la imagen primaria del producto
            primary_image = Image.query.filter_by(
                product_id=product.id,
                is_primary=True
            ).first()

            # Si no hay primaria, usar la que hizo match
            if not primary_image:
                primary_image = img

            # Retornar base64 cacheado (evita descargas de Cloudinary)
            image_url = primary_image.optimized_url if primary_image else None
        except Exception as e:
            print(f"❌ Error obteniendo imagen primaria: {e}")
            # CRITICAL: Hacer rollback para que queries posteriores funcionen
            db.session.rollback()
            # Si falla, usar la imagen que hizo match
            image_url = img.optimized_url if img else None

        # Preparar atributos dinámicos del producto (JSONB)
        product_attrs = {}
        product_url_value = None  # Siempre intentar extraer el link, aunque no esté expuesto
        try:
            if hasattr(product, 'attributes') and product.attributes:
                # 1) Siempre intentar obtener url_producto del JSON bruto (ignorar filtros de exposición)
                try:
                    raw_url = product.attributes.get('url_producto')
                    if isinstance(raw_url, dict):
                        # Algunos stores guardan { value: 'https://...' }
                        product_url_value = raw_url.get('value') or raw_url.get('url') or None
                    else:
                        product_url_value = raw_url
                except Exception as ie:
                    print(f"⚠️ Error extrayendo url_producto para {product.id}: {ie}")
                    product_url_value = None

                # 2) Aplicar filtros de exposición solo para el bloque de attributes
                if exposed_keys_cache is not None:
                    # Filtrar solo los atributos configurados para exponerse
                    product_attrs = {
                        k: v for k, v in product.attributes.items() if k in exposed_keys_cache
                    }
                else:
                    # Sin configuración, exponer todos los atributos (compatibilidad existente)
                    product_attrs = dict(product.attributes)
        except Exception as e:
            print(f"⚠️ Error leyendo atributos de producto {product.id}: {e}")
            product_attrs = {}

        # 🚀 FASE 3: Incluir optimizer_scores si están disponibles
        optimizer_scores = best_match.get('optimizer_scores')

        result = {
            "product_id": product.id,
            "name": product.name,
            "description": product.description or "Sin descripción",
            "image_url": image_url,
            "similarity": round(similarity, 4),
            "price": float(product.price) if product.price else None,
            "sku": product.sku,
            "stock": product.stock if hasattr(product, 'stock') and product.stock is not None else 0,
            "category": product.category.name if product.category else "Sin categoría",
            "category_boost": category_boost,
            "color_boost": color_boost,
            # Atributos dinámicos (filtrados si hay configuración)
            "attributes": product_attrs,
            # URL del producto si está configurada
            "product_url": product_url_value
        }

        # Agregar scores del optimizer si existen
        if optimizer_scores:
            result['optimizer'] = {
                'visual_score': round(optimizer_scores['visual_score'], 4),
                'metadata_score': round(optimizer_scores['metadata_score'], 4),
                'business_score': round(optimizer_scores['business_score'], 4),
                'final_score': round(optimizer_scores['final_score'], 4),
                'enabled': True
            }

        results.append(result)

        boost_indicator = "🚀" if category_boost else ""
        color_indicator = "🎨" if color_boost else ""
        optimizer_indicator = "🏯" if optimizer_scores else ""
        print(f"📦 DEBUG: Producto final añadido: {product.name} (similitud: {similarity:.4f}) {boost_indicator}{color_indicator}{optimizer_indicator}")

    print(f"🎯 DEBUG: Total productos únicos procesados: {len(results)}")

    # Ordenar por similitud y limitar resultados
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]


def _normalize_color_gender(color_str: str) -> str:
    """Normaliza género en nombres de colores para matching consistente."""
    if not color_str:
        return color_str
    mapping = {
        'NEGRA': 'NEGRO', 'BLANCA': 'BLANCO', 'ROJA': 'ROJO', 'AMARILLA': 'AMARILLO',
        'MORADA': 'MORADO', 'DORADA': 'DORADO', 'PLATEADA': 'PLATEADO', 'BRONCEADA': 'BRONCEADO'
    }
    u = str(color_str).strip().upper()
    return mapping.get(u, u)


def detect_dominant_color(image_data, client_id):
    """
    Detecta el color dominante en la imagen usando CLIP
    Usa los colores reales de los productos del cliente (dinámico)
    """
    try:
        # Obtener colores únicos desde JSONB attributes->>'color' (preferido)
        rows = db.session.execute(
            text(
                """
                SELECT DISTINCT UPPER(TRIM(attributes->>'color')) AS color
                FROM products
                WHERE client_id = :client_id
                  AND attributes ? 'color'
                  AND NULLIF(TRIM(attributes->>'color'), '') IS NOT NULL
                """
            ),
            {"client_id": client_id},
        ).fetchall()

        unique_colors = [r[0] for r in rows if r[0]]

        if not unique_colors:
            print("⚠️ No hay colores definidos en productos del cliente")
            return "unknown", 0.0

        print(f"🎨 Colores disponibles del cliente (JSONB): {unique_colors}")

        # Crear prompts dinámicos basados en los colores del cliente
        color_prompts = [f"a photo of {color.lower()} product" for color in unique_colors]

        # Convertir a imagen PIL
        from PIL import Image as PILImage
        pil_image = PILImage.open(io.BytesIO(image_data))

        # Obtener modelo CLIP
        model, processor = get_clip_model()

        # Generar embedding de imagen
        with torch.no_grad():
            image_inputs = processor(images=pil_image, return_tensors="pt")
            image_features = model.get_image_features(**image_inputs)
            image_embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Generar embeddings de texto para colores
            text_inputs = processor(text=color_prompts, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_color = unique_colors[best_idx]

            print(f"🎨 DETECCIÓN COLOR: {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"❌ Error en detección de color: {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_dominant_color_from_palette(image_data, colors_list):
    """
    Detecta el color dominante restringiendo la comparación a una paleta dada.
    """
    try:
        unique_colors = [c.strip() for c in colors_list if c and str(c).strip()]

        if not unique_colors:
            print("⚠️ Paleta de colores vacía para la categoría")
            return "unknown", 0.0

        print(f"🎨 Paleta de colores (categoría): {unique_colors}")

        # Crear prompts dinámicos basados en los colores de la categoría
        color_prompts = [f"a photo of {color.lower()} product" for color in unique_colors]

        # Convertir a imagen PIL
        from PIL import Image as PILImage
        pil_image = PILImage.open(io.BytesIO(image_data))

        # Obtener modelo CLIP
        model, processor = get_clip_model()

        # Generar embedding de imagen
        with torch.no_grad():
            image_inputs = processor(images=pil_image, return_tensors="pt")
            image_features = model.get_image_features(**image_inputs)
            image_embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Generar embeddings de texto para colores
            text_inputs = processor(text=color_prompts, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_color = unique_colors[best_idx]

            print(f"🎨 DETECCIÓN COLOR (categoría): {detected_color} (confianza: {best_score:.3f})")

            return detected_color, best_score

    except Exception as e:
        print(f"❌ Error en detección de color (paleta): {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_general_object(image_data, client_id=None):
    """
    Detecta QUÉ es el objeto en la imagen usando CLIP.
    """
    try:
        # Si hay client_id, usar las categorías del cliente
        if client_id:
            categories = Category.query.filter_by(
                client_id=client_id,
                is_active=True
            ).all()

            if categories:
                # Usar name_en de las categorías como términos de detección
                general_categories = []
                for cat in categories:
                    if cat.name_en:
                        general_categories.append(f"a photo of {cat.name_en.lower()}")
                    else:
                        general_categories.append(f"a photo of {cat.name.lower()}")

                print(f"🔍 Usando categorías del cliente para detección: {[c.split('of ')[1] for c in general_categories]}")
            else:
                print("⚠️ No hay categorías activas, usando detección genérica")
                general_categories = ["product", "item", "object"]
        else:
            # Detección genérica amplia para cualquier tipo de producto
            general_categories = [
                "product", "item", "object", "merchandise",
                "clothing", "apparel", "garment",
                "accessory", "tool", "equipment",
                "furniture", "decoration", "appliance"
            ]

        # Convertir a imagen PIL
        from PIL import Image as PILImage
        pil_image = PILImage.open(io.BytesIO(image_data))

        # Obtener modelo CLIP
        model, processor = get_clip_model()

        # Generar embedding de imagen
        with torch.no_grad():
            image_inputs = processor(images=pil_image, return_tensors="pt")
            image_features = model.get_image_features(**image_inputs)
            image_embedding = image_features / image_features.norm(dim=-1, keepdim=True)

            # Generar embeddings de texto para categorías
            text_inputs = processor(text=general_categories, return_tensors="pt", padding=True)
            text_features = model.get_text_features(**text_inputs)
            text_embeddings = text_features / text_features.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = torch.cosine_similarity(image_embedding, text_embeddings, dim=1)

            # Encontrar la mejor coincidencia
            best_idx = similarities.argmax().item()
            best_score = similarities[best_idx].item()
            detected_object = general_categories[best_idx]

            # Extraer solo el término del objeto (sin "a photo of")
            if "a photo of" in detected_object:
                detected_object = detected_object.replace("a photo of ", "").strip()

            print(f"🔍 DETECCIÓN GENERAL: {detected_object} (confianza: {best_score:.3f})")

            return detected_object, best_score

    except Exception as e:
        print(f"❌ Error en detección general: {e}")
        import traceback
        traceback.print_exc()
        return "unknown", 0.0


def detect_image_category_with_centroids(image_data, client_id, confidence_threshold=0.2):
    """
    Detecta la categoría de una imagen usando centroides de embeddings reales.
    """
    try:
        from app.blueprints.api import railway_log  # para logs consistentes en Railway
        railway_log(f" LOG: Iniciando detección centroides para cliente {client_id}")

        # 1. Obtener categorías activas del cliente
        categories = Category.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()

        if not categories:
            railway_log(f" LOG: No categorías para cliente {client_id}")
            return None, 0

        railway_log(f" LOG: {len(categories)} categorías encontradas")

        # 2. Generar embedding de la imagen nueva
        from PIL import Image as PILImage
        pil_image = PILImage.open(io.BytesIO(image_data))
        print(f"🖼️ DEBUG: Imagen preparada: {pil_image.size}")

        # 3. Obtener modelo CLIP
        model, processor = get_clip_model()
        print("🧩 DEBUG: Modelo CLIP obtenido")

        # 4. Generar embedding de imagen nueva
        with torch.no_grad():
            image_inputs = processor(
                images=pil_image,
                return_tensors="pt"
            )
            image_features = model.get_image_features(**image_inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            new_embedding = image_features.squeeze(0).numpy()

        print(f"🔍 DEBUG: Embedding generado: shape {new_embedding.shape}")

        # 5. Calcular similitudes contra centroides de cada categoría
        category_similarities = []

        for category in categories:
            # 🚀 USAR CENTROIDE DE BD DIRECTAMENTE
            centroid = category.get_centroid_embedding(auto_calculate=False)
            railway_log(f" LOG: {category.name} - centroide {'OK' if centroid is not None else 'NULL'}")

            if centroid is not None:
                # Calcular similitud coseno
                similarity = np.dot(new_embedding, centroid) / (np.linalg.norm(new_embedding) * np.linalg.norm(centroid))
                category_similarities.append({
                    'category': category,
                    'similarity': float(similarity)
                })
                railway_log(f" LOG: {category.name}: similitud {similarity:.4f}")
            else:
                railway_log(f" LOG: {category.name} SIN CENTROIDE en BD")

        if not category_similarities:
            railway_log(f" LOG: NO HAY SIMILITUDES - sin centroides válidos")
            return None, 0

        # 6. Encontrar la mejor coincidencia con margen de victoria y desempate
        # Ordenar por similitud descendente
        category_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        best_match = category_similarities[0]
        best_category = best_match['category']
        best_score = best_match['similarity']
        second_score = category_similarities[1]['similarity'] if len(category_similarities) > 1 else -1.0

        railway_log(f" LOG: MEJOR: {best_category.name} = {best_score:.4f} | SEGUNDO = {second_score:.4f}")

        # Margen de victoria mínimo para aceptar directamente la categoría ganadora
        MARGIN_DELTA = 0.03  # 3 puntos de similitud coseno

        # Si el margen es muy chico, usamos un desempate con la detección general
        if second_score >= 0 and (best_score - second_score) < MARGIN_DELTA:
            railway_log(f" LOG: MARGEN PEQUEÑO ({best_score - second_score:.4f} < {MARGIN_DELTA}), aplicando desempate por objeto general")
            try:
                detected_object, object_confidence = detect_general_object(image_data, client_id)
                railway_log(f" LOG: OBJETO GENERAL = {detected_object} (conf {object_confidence:.3f})")

                if object_confidence >= 0.20:  # usar con umbral bajo, solo como desempate
                    # Comparar el objeto detectado con los nombres de las categorías (name y name_en)
                    top2 = category_similarities[:2]

                    def cat_matches_object(cat, obj):
                        """Verifica si el objeto detectado está relacionado con la categoría"""
                        cat_name = (cat.name or '').lower()
                        cat_name_en = (cat.name_en or '').lower()
                        obj_lower = obj.lower()

                        # Match directo o por inclusión
                        return obj_lower in cat_name or obj_lower in cat_name_en or \
                               cat_name in obj_lower or cat_name_en in obj_lower

                    best_matches = cat_matches_object(best_category, detected_object)
                    second_cat = top2[1]['category'] if len(top2) > 1 else None
                    second_matches = cat_matches_object(second_cat, detected_object) if second_cat else False

                    if not best_matches and second_matches:
                        # Elegir la segunda si está en el grupo preferido
                        railway_log(f" LOG: DESEMPATE → Preferimos '{second_cat.name}' por concordar con objeto '{detected_object}'")
                        best_category = second_cat
                        best_score = top2[1]['similarity']
                    else:
                        railway_log(f" LOG: Desempate mantiene categoría original (best={best_matches}, second={second_matches})")
                else:
                    railway_log(" LOG: Desempate no aplicado (baja confianza del objeto)")
            except Exception as e:
                railway_log(f" LOG: Error en desempate por objeto general: {e}")

        # 7. Verificar umbral de confianza
        if best_score >= confidence_threshold:
            railway_log(f" LOG: DETECTADO - {best_category.name} (conf: {best_score:.4f})")
            return best_category, best_score
        else:
            railway_log(f" LOG: RECHAZADO - {best_score:.4f} < {confidence_threshold}")
            return None, best_score

    except Exception as e:
        print(f"❌ ERROR en detección por centroides: {e}")
        import traceback
        traceback.print_exc()
        return None, 0


def detect_image_category(image_data, client_id, confidence_threshold=0.2):
    """
    Función de detección por prompts (obsoleta, usa centroides como fallback)
    """
    try:
        print(f"🎯 DEBUG: Usando método de centroides en lugar de prompts")
        return detect_image_category_with_centroids(image_data, client_id, confidence_threshold)

    except Exception as e:
        print(f"❌ ERROR en detección de categoría: {e}")
        import traceback
        traceback.print_exc()
        return None, 0
