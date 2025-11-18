"""
Generador automático de sinónimos usando GPT-4
Auto-genera términos alternativos para categorías y productos
"""

import os
import openai
from typing import List, Optional
import json

# Configurar OpenAI (usar misma key que visual search)
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_synonyms_for_category(
    name: str,
    name_en: Optional[str] = None,
    description: Optional[str] = None,
    client_industry: Optional[str] = None
) -> List[str]:
    """
    Genera sinónimos para una categoría usando GPT-4.

    Args:
        name: Nombre de la categoría en español (ej: "shores tiro alto")
        name_en: Nombre en inglés (ej: "high waist shorts")
        description: Descripción de la categoría
        client_industry: Industria del cliente (ej: "textil", "deportivo")

    Returns:
        Lista de sinónimos: ["short", "shorts", "bermuda", "short rojo", ...]
    """

    # Si no hay API key, retornar fallback básico
    if not openai.api_key:
        print("⚠️ OPENAI_API_KEY no configurada, usando fallback básico")
        return _generate_fallback_synonyms(name, name_en)

    # Construir prompt contextual
    prompt = f"""Eres un experto en e-commerce de moda. Tu tarea es generar sinónimos y variaciones de búsqueda para una categoría de productos.

CATEGORÍA:
- Nombre (ES): {name}
- Nombre (EN): {name_en or 'N/A'}
- Descripción: {description or 'N/A'}
- Industria: {client_industry or 'moda/textil'}

GENERA una lista de sinónimos y variaciones que un usuario podría escribir al buscar esta categoría. Incluye:
1. Variaciones ortográficas (singular/plural)
2. Términos en español e inglés
3. Nombres coloquiales o regionalismos
4. Combinaciones comunes con colores básicos (ej: "short rojo", "short negro", "short blanco")
5. Abreviaciones comunes

FORMATO: Devuelve SOLO una lista separada por comas, sin numeración ni explicaciones.

EJEMPLO para "remeras manga corta":
remera,remeras,camiseta,camisetas,playera,playeras,shirt,t-shirt,tshirt,polo,remera manga corta,camiseta manga corta,short sleeve,short sleeve shirt,remera blanca,remera negra,remera roja

AHORA GENERA para "{name}":"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # o "gpt-3.5-turbo" si querés más económico
            messages=[
                {"role": "system", "content": "Eres un experto en sinónimos de moda y e-commerce. Genera listas completas y precisas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Más determinista
            max_tokens=300
        )

        # Parsear respuesta
        synonyms_text = response.choices[0].message.content.strip()
        synonyms = [s.strip().lower() for s in synonyms_text.split(',') if s.strip()]

        # Agregar el nombre original y name_en al principio
        if name.lower() not in synonyms:
            synonyms.insert(0, name.lower())
        if name_en and name_en.lower() not in synonyms:
            synonyms.insert(1, name_en.lower())

        # Deduplicar manteniendo orden
        seen = set()
        unique_synonyms = []
        for syn in synonyms:
            if syn not in seen:
                seen.add(syn)
                unique_synonyms.append(syn)

        print(f"✅ GPT-4 generó {len(unique_synonyms)} sinónimos para '{name}'")
        return unique_synonyms

    except Exception as e:
        print(f"❌ Error llamando GPT-4: {e}")
        # Fallback: retornar sinónimos básicos
        return _generate_fallback_synonyms(name, name_en)


def _generate_fallback_synonyms(name: str, name_en: Optional[str] = None) -> List[str]:
    """
    Genera sinónimos básicos sin GPT-4 (fallback).
    """
    synonyms = [name.lower()]

    if name_en:
        synonyms.append(name_en.lower())

    # Variaciones comunes de plural/singular
    if name.lower().endswith('s'):
        # Si termina en 's', agregar sin 's'
        synonyms.append(name.lower()[:-1])
    else:
        # Si no termina en 's', agregar con 's'
        synonyms.append(name.lower() + 's')

    # Combinaciones con colores básicos
    colors = ['rojo', 'negro', 'blanco', 'azul', 'verde']
    for color in colors:
        synonyms.append(f"{name.lower()} {color}")

    # Deduplicar
    return list(dict.fromkeys(synonyms))


def generate_synonyms_for_product(
    product_name: str,
    category_name: str,
    attributes: dict = None
) -> List[str]:
    """
    Genera sinónimos para un producto específico.

    Ejemplo:
    - Input: "short simil pollera rojo", category="shores tiro alto", attributes={"color": "rojo"}
    - Output: ["short rojo", "short pollera", "pollera rojo", "red short", ...]
    """

    if not openai.api_key:
        # Fallback básico
        synonyms = [product_name.lower()]
        if attributes and 'color' in attributes:
            synonyms.append(f"{category_name.lower()} {attributes['color'].lower()}")
        return list(dict.fromkeys(synonyms))

    attrs_text = ", ".join([f"{k}={v}" for k, v in (attributes or {}).items()])

    prompt = f"""Genera sinónimos de búsqueda para este producto:

PRODUCTO: {product_name}
CATEGORÍA: {category_name}
ATRIBUTOS: {attrs_text or 'N/A'}

Genera variaciones que un usuario escribiría al buscar este producto específico. Combina:
- Nombre del producto con atributos (ej: "short rojo")
- Variaciones de color en español/inglés
- Términos descriptivos del producto

FORMATO: Lista separada por comas, máximo 10 términos.

SINÓNIMOS:"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Más económico para productos
            messages=[
                {"role": "system", "content": "Eres un experto en sinónimos de productos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )

        synonyms_text = response.choices[0].message.content.strip()
        synonyms = [s.strip().lower() for s in synonyms_text.split(',') if s.strip()]

        # Deduplicar
        return list(dict.fromkeys(synonyms))

    except Exception as e:
        print(f"❌ Error generando sinónimos de producto: {e}")
        return [product_name.lower()]


def regenerate_synonyms_for_category(category_id: str):
    """
    Regenera sinónimos para una categoría existente.
    Útil para endpoint de regeneración manual.
    """
    from app.models.category import Category
    from app import db

    category = Category.query.get(category_id)
    if not category:
        raise ValueError(f"Categoría {category_id} no encontrada")

    synonyms = generate_synonyms_for_category(
        name=category.name,
        name_en=category.name_en,
        description=category.description,
        client_industry=category.client.industry if category.client else None
    )

    category.alternative_terms = ','.join(synonyms)
    db.session.commit()

    return synonyms
