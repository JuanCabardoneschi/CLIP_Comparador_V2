"""
Servicio para auto-completar atributos de productos usando CLIP
Analiza las imágenes y detecta atributos visuales automáticamente
"""
import torch
from PIL import Image
import requests
from io import BytesIO
import json
import numpy as np
from typing import Dict, List, Tuple, Optional
from app.models import Product, Image as ProductImage, ProductAttributeConfig
from app import db
from app.blueprints.embeddings import get_clip_model  # Reutilizar modelo compartido

# Tags contextuales expandidos para búsquedas conceptuales
# Categorizados por ocasión, funcionalidad y características visuales

# Ocasión / Uso
OCCASION_TAGS = [
    "fiesta", "boda", "gala", "evento_formal", "deporte", "gym", "running",
    "futbol", "basketball", "yoga", "trabajo", "oficina", "profesional",
    "casual", "diario", "relax", "outdoor", "playa", "concierto"
]

# Funcionalidad
FUNCTIONAL_TAGS = [
    "protege_sol", "protege_lluvia", "cubre_bien", "cobertura_total",
    "transpirable", "comodo", "flexible", "elastico", "ajustable",
    "liviano", "resistente", "duradero", "impermeable"
]

# Estilo visual
VISUAL_STYLE_TAGS = [
    "elegante", "casual", "deportivo", "moderno", "clasico", "vintage",
    "minimalista", "colorido", "neutro", "brillante", "mate",
    "estampado", "liso", "texturizado"
]

# Demográfico
DEMOGRAPHIC_TAGS = [
    "unisex", "masculino", "femenino", "infantil", "juvenil", "adulto"
]

# Consolidado para clasificación
TAG_OPTIONS = (
    OCCASION_TAGS +
    FUNCTIONAL_TAGS +
    VISUAL_STYLE_TAGS +
    DEMOGRAPHIC_TAGS
)

# Templates de prompts por tipo de atributo
ATTRIBUTE_PROMPT_TEMPLATES = {
    "color": "a {value} colored {category}",
    "colour": "a {value} colored {category}",
    "color_principal": "a {value} colored {category}",
    "material": "a {category} made of {value}",
    "tela": "a {category} made of {value}",
    "fabric": "a {category} made of {value}",
    "estilo": "a {value} style {category}",
    "style": "a {value} style {category}",
    "tipo": "a {value} type {category}",
    "type": "a {value} type {category}",
    "patron": "a {category} with {value} pattern",
    "pattern": "a {category} with {value} pattern",
    "_default": "a photo of a {value} {category}"
}


class AttributeAutofillService:
    """Servicio para auto-completar atributos usando análisis CLIP"""

    @classmethod
    def _ensure_model_loaded(cls):
        """Obtiene el modelo CLIP compartido del sistema (sin duplicar carga)"""
        # Usar el modelo compartido del sistema en lugar de cargar uno propio
        return get_clip_model()

    @classmethod
    def _get_prompt_template(cls, attribute_key: str) -> str:
        """Determina el template de prompt adecuado para un atributo"""
        key_lower = attribute_key.lower()
        return ATTRIBUTE_PROMPT_TEMPLATES.get(key_lower, ATTRIBUTE_PROMPT_TEMPLATES["_default"])

    @classmethod
    def _classify_attribute(cls, image: Image.Image, attribute_name: str,
                          options: List[str], category_context: str) -> Tuple[str, float]:
        """
        Clasifica un atributo usando CLIP comparando la imagen con opciones textuales

        Args:
            image: Imagen PIL a analizar
            attribute_name: Nombre del atributo (ej: 'color', 'material')
            options: Lista de valores posibles (ej: ['ROJO', 'AZUL', 'VERDE'])
            category_context: Contexto de categoría (ej: 'camisa', 'delantal')

        Returns:
            Tupla (mejor_opción, confianza)
        """
        model, processor = cls._ensure_model_loaded()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Obtener template de prompt adecuado
        prompt_template = cls._get_prompt_template(attribute_name)

        # Crear prompts textuales para cada opción
        text_prompts = [
            prompt_template.replace("{value}", option).replace("{category}", category_context)
            for option in options
        ]

        # Preprocesar imagen y textos
        inputs = processor(
            text=text_prompts,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(device)

        # Generar embeddings
        with torch.no_grad():
            outputs = model(**inputs)

            # Normalizar embeddings
            image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
            text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)

            # Calcular similitudes (imagen con cada texto)
            similarities = (image_embeds @ text_embeds.T).cpu().numpy()[0]

        # Encontrar la opción con mayor similitud
        best_idx = similarities.argmax()
        best_option = options[best_idx]
        confidence = float(similarities[best_idx])

        return best_option, confidence

    @classmethod
    def _classify_tags(cls, image: Image.Image, tag_options: List[str],
                      threshold: float = 0.25, category_context: str = "garment") -> List[Tuple[str, float]]:
        """
        Clasifica múltiples tags que aplican a la imagen

        Returns:
            Lista de tuplas (tag, confianza) con confianza superior al umbral
        """
        model, processor = cls._ensure_model_loaded()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Crear prompts textuales para cada tag
        text_prompts = [f"a {tag} style {category_context}" for tag in tag_options]

        # Preprocesar imagen y textos
        inputs = processor(
            text=text_prompts,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(device)

        # Generar embeddings
        with torch.no_grad():
            outputs = model(**inputs)

            # Normalizar embeddings
            image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
            text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)

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
    def _download_image(cls, url: str) -> Optional[Image.Image]:
        """Descarga una imagen desde URL y la convierte a PIL Image"""
        try:
            # Aplicar transformación de Cloudinary para centrar sujeto
            if "/upload/" in url:
                url = url.replace("/upload/", "/upload/c_fill,g_auto,w_800,h_800/")

            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert('RGB')
        except Exception as e:
            print(f"⚠️ Error descargando imagen {url}: {e}")
            return None

    @classmethod
    def autofill_product_attributes(cls, product: Product, overwrite: bool = False) -> Dict[str, any]:
        """
        Auto-completa atributos de un producto usando CLIP

        Args:
            product: Instancia del producto a analizar
            overwrite: Si True, sobrescribe atributos existentes. Si False, solo completa vacíos

        Returns:
            Dict con resultados: {'attributes': {...}, 'tags': str, 'success': bool, 'message': str}
        """
        try:
            # Validar que el producto tenga imágenes
            images = ProductImage.query.filter_by(product_id=product.id).all()
            if not images:
                return {
                    'success': False,
                    'message': 'Producto sin imágenes para analizar',
                    'attributes': {},
                    'tags': ''
                }

            # Obtener configuración de atributos del cliente
            attribute_configs = ProductAttributeConfig.query.filter_by(
                client_id=product.client_id,
                type='list'
            ).all()

            if not attribute_configs:
                return {
                    'success': False,
                    'message': 'Cliente sin atributos configurados para autofill',
                    'attributes': {},
                    'tags': ''
                }

            # Preparar opciones de atributos
            attribute_options = {}
            for config in attribute_configs:
                if config.options and isinstance(config.options, dict) and 'values' in config.options:
                    values = config.options['values']
                    if values:
                        attribute_options[config.key] = values

            if not attribute_options:
                return {
                    'success': False,
                    'message': 'No hay atributos tipo lista con valores configurados',
                    'attributes': {},
                    'tags': ''
                }

            # Contexto de categoría para prompts
            category_ctx = product.category.name.lower() if product.category else "producto"

            # Acumuladores de resultados por imagen
            all_attributes = {attr: {} for attr in attribute_options.keys()}
            all_tags = {}

            print(f"🔍 Analizando {len(images)} imagen(es) del producto {product.name}...")

            # Analizar cada imagen
            for img in images:
                # Descargar imagen
                pil_image = cls._download_image(img.display_url)
                if not pil_image:
                    continue

                # Peso de la imagen (primaria tiene más peso)
                weight = 1.5 if img.is_primary else 1.0

                # Clasificar cada atributo
                for attr_name, options in attribute_options.items():
                    best_option, confidence = cls._classify_attribute(
                        pil_image, attr_name, options, category_ctx
                    )

                    # Acumular votos ponderados por confianza
                    if confidence > 0.2:
                        if best_option not in all_attributes[attr_name]:
                            all_attributes[attr_name][best_option] = 0
                        all_attributes[attr_name][best_option] += confidence * weight

                # Clasificar tags relevantes (threshold MÁS BAJO para capturar más contexto semántico)
                relevant_tags = cls._classify_tags(pil_image, TAG_OPTIONS,
                                                  threshold=0.15, category_context=category_ctx)
                for tag, confidence in relevant_tags:
                    if tag not in all_tags:
                        all_tags[tag] = 0
                    all_tags[tag] += confidence * weight

            # Consolidar atributos finales
            detected_attributes = {}
            current_attributes = product.attributes or {}

            for attr_name, votes in all_attributes.items():
                if votes:
                    # Elegir el atributo con mayor peso acumulado
                    best_option = max(votes.items(), key=lambda x: x[1])

                    # Solo agregar si:
                    # 1. overwrite=True, O
                    # 2. El atributo no existe en el producto, O
                    # 3. El atributo existe pero está vacío
                    if overwrite or attr_name not in current_attributes or not current_attributes.get(attr_name):
                        detected_attributes[attr_name] = best_option[0]
                        print(f"  ✓ {attr_name}: {best_option[0]} (conf: {best_option[1]:.2f})")
                    else:
                        print(f"  ⊘ {attr_name}: Ya tiene valor '{current_attributes[attr_name]}' (detectado: {best_option[0]})")

            # Consolidar tags contextuales (mezclar existentes + nuevos)
            detected_tags = ""
            if all_tags:
                sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:8]
                new_tag_names = [tag for tag, _ in sorted_tags]

                # Mezclar con tags existentes (evitar duplicados)
                existing_tags = []
                if product.tags:
                    existing_tags = [t.strip() for t in product.tags.split(',') if t.strip()]

                # Combinar: primero los nuevos (más relevantes), luego los viejos no duplicados
                combined_tags = new_tag_names.copy()
                for old_tag in existing_tags:
                    if old_tag not in combined_tags:
                        combined_tags.append(old_tag)

                # Limitar a 12 tags totales para no saturar
                final_tags = combined_tags[:12]
                detected_tags = ", ".join(final_tags)

                # Mostrar tags con confianza para debugging
                tags_debug = ", ".join([f"{tag}({conf:.2f})" for tag, conf in sorted_tags])
                print(f"  ✓ Tags nuevos detectados: {tags_debug}")
                if existing_tags:
                    print(f"  ℹ️ Tags existentes preservados: {', '.join([t for t in existing_tags if t in final_tags])}")

            return {
                'success': True,
                'message': f'Detectados {len(detected_attributes)} atributos',
                'attributes': detected_attributes,
                'tags': detected_tags
            }

        except Exception as e:
            print(f"❌ Error en autofill de atributos: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'attributes': {},
                'tags': ''
            }
