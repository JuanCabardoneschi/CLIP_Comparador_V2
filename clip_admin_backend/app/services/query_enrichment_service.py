"""
Servicio para enriquecer queries de búsqueda con tags inferidos usando CLIP
Genera embeddings fusionados y tags semánticos desde texto e imagen opcional
"""
import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests
from io import BytesIO
import hashlib
import json
from typing import Dict, List, Tuple, Optional
from functools import lru_cache

# Tags genéricos detectables por contexto visual/textual
INFERENCE_TAG_OPTIONS = [
    "formal", "casual", "deportivo", "elegante", "moderno", "clásico",
    "vintage", "urbano", "profesional", "juvenil", "trabajo", "fiesta",
    "verano", "invierno", "premium", "económico", "cómodo", "ajustado"
]

# Templates para generar frases de clasificación
TAG_PROMPT_TEMPLATES = {
    "color": "a {value} colored {category}",
    "material": "a {category} made of {value}",
    "style": "a {value} style {category}",
    "context": "a {value} {category}",
    "_default": "a {value} {category}"
}


class QueryEnrichmentService:
    """Servicio para enriquecer búsquedas con tags inferidos y fusión de embeddings"""

    _model = None
    _processor = None
    _device = None
    _cache = {}  # Cache simple en memoria {hash: result}

    @classmethod
    def _ensure_model_loaded(cls):
        """Carga el modelo CLIP si aún no está cargado (lazy loading)"""
        if cls._model is None:
            print("🔮 Cargando modelo CLIP para QueryEnrichment...")
            cls._device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = "openai/clip-vit-base-patch16"
            cls._model = CLIPModel.from_pretrained(model_name).to(cls._device)
            cls._processor = CLIPProcessor.from_pretrained(model_name)
            print(f"✅ Modelo CLIP para enrichment cargado en {cls._device}")

    @classmethod
    def _download_image(cls, url: str) -> Optional[Image.Image]:
        """Descarga una imagen desde URL y la convierte a PIL Image"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert('RGB')
            return image
        except Exception as e:
            print(f"⚠️ Error descargando imagen para enrichment: {e}")
            return None

    @classmethod
    def _classify_tags_from_image(cls, image: Image.Image, tag_options: List[str],
                                  threshold: float = 0.25, category_context: str = "product") -> List[Tuple[str, float]]:
        """
        Clasifica tags relevantes desde una imagen usando CLIP

        Args:
            image: Imagen PIL a analizar
            tag_options: Lista de tags candidatos
            threshold: Umbral de confianza mínimo
            category_context: Contexto de categoría para prompts

        Returns:
            Lista de tuplas (tag, confianza) ordenadas por confianza descendente
        """
        cls._ensure_model_loaded()

        # Crear prompts textuales para cada tag
        text_prompts = [f"a {tag} style {category_context}" for tag in tag_options]

        # Preprocesar imagen y textos
        inputs = cls._processor(
            text=text_prompts,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(cls._device)

        # Generar embeddings
        with torch.no_grad():
            outputs = cls._model(**inputs)

            # Normalizar embeddings
            image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
            text_embeds = outputs.text_embeds / text_embeds.norm(dim=-1, keepdim=True)

            # Calcular similitudes
            similarities = (image_embeds @ text_embeds.T).cpu().numpy()[0]

        # Filtrar tags con confianza superior al umbral
        relevant_tags = []
        for i, tag in enumerate(tag_options):
            if similarities[i] > threshold:
                relevant_tags.append((tag, float(similarities[i])))

        # Ordenar por confianza descendente
        relevant_tags.sort(key=lambda x: x[1], reverse=True)

        return relevant_tags

    @classmethod
    def _generate_cache_key(cls, query_text: str, image_url: Optional[str], client_id: str) -> str:
        """Genera un hash único para cachear resultados de inferencia"""
        key_data = f"{query_text}|{image_url or 'noimg'}|{client_id}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()

    @classmethod
    def enrich_query(cls,
                    query_text: str,
                    detected_category: Optional[str] = None,
                    detected_color: Optional[str] = None,
                    detected_contexts: Optional[List[str]] = None,
                    image_url: Optional[str] = None,
                    client_id: str = "",
                    use_cache: bool = True) -> Dict:
        """
        Enriquece una query de búsqueda con tags inferidos y genera frases contextuales

        Args:
            query_text: Texto de búsqueda original
            detected_category: Categoría detectada (opcional)
            detected_color: Color detectado por normalizador (opcional)
            detected_contexts: Lista de contextos detectados (ej: ['casual', 'deportivo'])
            image_url: URL de imagen para análisis visual (opcional)
            client_id: ID del cliente para cache
            use_cache: Usar caché de resultados

        Returns:
            Dict con:
                - tag_phrases: List[str] - Frases generadas para fusión
                - inferred_tags: List[Tuple[str, float]] - Tags inferidos con confianza
                - enriched_text: str - Texto enriquecido con tags
        """
        try:
            # Verificar cache
            cache_key = cls._generate_cache_key(query_text, image_url, client_id)
            if use_cache and cache_key in cls._cache:
                print(f"💾 CACHE HIT: enrichment para query '{query_text[:30]}...'")
                return cls._cache[cache_key]

            category_ctx = detected_category or "product"
            tag_phrases = []
            inferred_tags = []

            # 1. Tags desde normalizador (color, contextos)
            if detected_color:
                tag_phrases.append(f"a {detected_color} colored {category_ctx}")

            if detected_contexts:
                for ctx in detected_contexts:
                    try:
                        term = str(ctx).strip().lower()
                        if term:
                            tag_phrases.append(f"a {term} style {category_ctx}")
                    except Exception:
                        pass

            # 2. Tags desde imagen (si disponible)
            if image_url:
                image = cls._download_image(image_url)
                if image:
                    print(f"🖼️ Analizando imagen para enrichment...")
                    visual_tags = cls._classify_tags_from_image(
                        image,
                        INFERENCE_TAG_OPTIONS,
                        threshold=0.25,
                        category_context=category_ctx
                    )

                    # Agregar top 3 tags visuales
                    for tag, conf in visual_tags[:3]:
                        inferred_tags.append((tag, conf))
                        tag_phrases.append(f"a {tag} style {category_ctx}")

            # 3. Generar texto enriquecido
            enriched_text = query_text
            if inferred_tags:
                top_tags = [tag for tag, _ in inferred_tags[:3]]
                enriched_text = f"{query_text} {' '.join(top_tags)}"

            result = {
                'tag_phrases': tag_phrases,
                'inferred_tags': inferred_tags,
                'enriched_text': enriched_text,
                'category_context': category_ctx
            }

            # Guardar en cache
            if use_cache:
                cls._cache[cache_key] = result

            print(f"🔮 ENRICHED: {len(tag_phrases)} frases, {len(inferred_tags)} tags")

            return result

        except Exception as e:
            print(f"❌ Error en query enrichment: {e}")
            import traceback
            traceback.print_exc()
            return {
                'tag_phrases': [],
                'inferred_tags': [],
                'enriched_text': query_text,
                'category_context': detected_category or "product"
            }

    @classmethod
    def clear_cache(cls):
        """Limpia el cache de inferencias"""
        cls._cache.clear()
        print("🗑️ Cache de QueryEnrichment limpiado")

    @classmethod
    def get_cache_stats(cls) -> Dict:
        """Retorna estadísticas del cache"""
        return {
            'size': len(cls._cache),
            'keys': list(cls._cache.keys())[:10]  # Primeras 10 keys
        }
