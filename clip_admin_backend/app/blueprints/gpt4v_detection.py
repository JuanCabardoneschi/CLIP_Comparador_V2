"""
Blueprint para detección de categorías con GPT-4 Vision (Multi-categoría)
Detecta TODAS las prendas visibles y mapea a categorías del cliente
"""
import os
import io
import base64
import json
import logging
from flask import Blueprint, request, jsonify, render_template
from PIL import Image
from openai import OpenAI

logger = logging.getLogger(__name__)

gpt4v_bp = Blueprint('gpt4v_detection', __name__, url_prefix='/api/gpt4v')

# Cliente OpenAI (lazy loading)
_openai_client = None


def get_openai_client():
    """Obtener cliente OpenAI (lazy loading)"""
    global _openai_client

    if _openai_client is not None:
        return _openai_client

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada en .env o Railway")

    _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def build_categories_catalog_with_hints(categories_list, client_id):
    """
    Construir catálogo de categorías con aclaraciones selectivas (vision_hint) para Vision.

    Args:
        categories_list: list[str] - Nombres de categorías
        client_id: str - ID del cliente

    Returns:
        tuple: (catalog_string, hints_string)
    """
    from app.models.category import Category

    # Categorías en mayúsculas entre comillas
    categories_upper = [f'"{cat.upper()}"' for cat in categories_list]
    catalog = ", ".join(categories_upper)

    # Obtener hints solo de categorías que tengan
    hints_lines = []
    for cat_name in categories_list:
        cat = Category.query.filter_by(
            name=cat_name,
            client_id=client_id
        ).first()

        if cat and cat.vision_hint and cat.vision_hint.strip():
            hint_text = cat.vision_hint.strip()
            # Si el hint empieza con "vs" es una comparación
            if hint_text.lower().startswith('vs '):
                hints_lines.append(f'- "{cat_name.upper()}" {hint_text}')
            else:
                hints_lines.append(f'- "{cat_name.upper()}": {hint_text}')

    hints_section = ""
    if hints_lines:
        hints_section = "\n\n⚠️ ACLARACIONES IMPORTANTES:\n" + "\n".join(hints_lines)

    return catalog, hints_section


def detect_categories_with_gpt4v(image_data, categories_list, client=None):
    """
    Detectar TODAS las categorías/prendas en una imagen usando GPT-4 Vision

    Args:
        image_data: bytes o PIL.Image
        categories_list: list[str] - Categorías disponibles del cliente
        client: Client model instance (opcional) - Para acceder a client.id y client.industry

    Returns:
        dict: {
            'prendas': [
                {
                    'tipo': str,
                    'color': str,
                    'confianza': str,
                    'categoria_sugerida': str | null
                }
            ],
            'mensaje_usuario': str,
            'raw_response': str
        }
    """
    try:
        client = get_openai_client()

        # Convertir imagen a base64
        if isinstance(image_data, bytes):
            image_bytes = image_data
        elif isinstance(image_data, Image.Image):
            buffer = io.BytesIO()
            image_data.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
        else:
            raise ValueError(f"Tipo de imagen inválido: {type(image_data)}")

        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # Extraer datos del cliente
        client_id = client.id if client else None
        industry = client.industry if client and hasattr(client, 'industry') else 'general'
        industry_context = f" (industria: {industry})" if industry and industry != 'general' else ""

        # Construir catálogo (hints eliminados)
        catalog, hints_section = build_categories_catalog_with_hints(categories_list, client_id)

        # Prompt optimizado del usuario (multi-categoría con mapeo dinámico)
        prompt = f"""Analiza la imagen y detecta TODOS los productos comercializables visibles{industry_context}.

CATÁLOGO: CATEGORÍAS DISPONIBLES (USAR EXACTAMENTE COMO APARECEN)
{catalog}{hints_section}

REGLAS DE MAPEO A CATEGORÍAS:
1) Para CADA producto detectado, elige la categoría MÁS ADECUADA de la lista por similitud conceptual.
2) Devuelve el nombre EXACTO en MAYÚSCULAS tal como aparece en la lista (entre comillas).
3) IMPORTANTE: Compara sin importar mayúsculas/minúsculas. Ej: si detectas "top" → busca "TOP" en la lista.
4) Si ninguna categoría aplica de forma razonable → usa null.
5) NO inventes categorías ni modifiques nombres.

Para CADA producto identifica:
- tipo: nombre claro y específico del producto
- color: color principal percibido
- confianza: alta | media | baja
- categoria_sugerida: nombre EXACTO EN MAYÚSCULAS de la lista o null

REGLAS DE COLOR:
- Usa nombres comunes: blanco, negro, azul, rojo, verde, amarillo, marrón, beige, gris, rosa, naranja, morado
- No confundas tonos cálidos con grises: si ves amarillento/anaranjado → marrón/beige; si ves azulado → gris

REGLAS GENERALES:
    - Lista TODOS los productos visibles que puedan comercializarse (pueden ser varios)
    - No inventes productos que no estén claramente visibles
    - Si hay dudas entre dos categorías, elige la más cercana conceptualmente de la lista; si la duda es alta → null

EJEMPLOS (GENÉRICOS):
- Producto del catálogo visible → usa la categoría relacionada si existe en la lista; si no, null
- Si el producto no coincide con ninguna categoría del catálogo → null
- Si la imagen no contiene productos comercializables del catálogo → devuelve array vacío

RESPUESTA (JSON ESTRICTO):
{{
    "prendas": [
        {{"tipo": "nombre_producto", "color": "color_principal", "confianza": "alta", "categoria_sugerida": null}}
    ],
    "mensaje_usuario": "Descripción detallada (2-3 oraciones) de lo que el usuario busca basado en los productos detectados. Menciona colores, tipos de productos y características. Si algún producto NO tiene categoría disponible en el catálogo, menciona explícitamente qué producto no se comercializa."
}}"""

        logger.info(f"🔍 GPT-4V detectando prendas (multi-cat) para cliente {client_id or 'N/A'}...")

        # 📝 LOGGING: Guardar prompt completo en archivo .txt
        try:
            from datetime import datetime
            # DEBUG: Log de prompt deshabilitado en producción (no existe carpeta logs en Railway)
            pass
        except Exception as log_err:
            print(f"⚠️ Error guardando prompt: {log_err}")
            logger.warning(f"⚠️ No se pudo guardar log del prompt: {log_err}")

        # Llamada a GPT-4 Vision (GPT-4o reemplaza gpt-4-vision-preview deprecado)
        response = client.chat.completions.create(
            model="gpt-4o",  # GPT-4 Omni con capacidades de visión
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high"  # Alta calidad para mejor detección
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.1  # Muy baja para respuestas consistentes
        )

        answer = response.choices[0].message.content
        logger.info(f"💬 Respuesta GPT-4V:\n{answer}")

        # Parsear respuesta JSON
        try:
            # Intentar extraer JSON del markdown si viene con ```json
            if "```json" in answer:
                json_str = answer.split("```json")[1].split("```")[0].strip()
            elif "```" in answer:
                json_str = answer.split("```")[1].split("```")[0].strip()
            else:
                json_str = answer.strip()

            result = json.loads(json_str)
            result['raw_response'] = answer

            logger.info(f"✅ Prendas detectadas: {len(result.get('prendas', []))}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON de GPT-4V: {e}")
            logger.error(f"Respuesta recibida: {answer}")

            # Fallback: retornar respuesta raw
            return {
                'prendas': [],
                'mensaje_usuario': 'Error parseando respuesta de GPT-4V',
                'raw_response': answer,
                'parse_error': str(e)
            }

    except Exception as e:
        logger.error(f"❌ Error en detección GPT-4V: {str(e)}", exc_info=True)
        raise
