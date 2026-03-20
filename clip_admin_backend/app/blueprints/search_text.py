#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NUEVO SISTEMA DE BÚSQUEDA TEXTUAL V2
Two-Stage Retrieval: SQL Fuzzy Match + CLIP Reranking
"""

from flask import Blueprint, request, jsonify
from flask_cors import CORS
from app import db
from app.utils.logging_config import log_error, log_nlp, log_verbose, log_search, LogCategory
from app.utils.system_config import system_config
from app.models.client import Client
from app.models.category import Category
from app.models.product import Product
from app.models.image import Image
from app.models.search_log import SearchLog
from sqlalchemy import text, func
import time
import numpy as np
import torch

# Importar CLIP
from app.blueprints.embeddings import get_clip_model
from typing import List, Set
import os

# 🆕 Importar proveedor de perfiles de búsqueda
from app.services.search_profiles_service import SearchProfilesService

# Reutilizar normalizador spaCy del blueprint API (sin duplicar lógica)
try:
    from app.blueprints.api import _get_spacy_nlp  # type: ignore
except Exception:
    _get_spacy_nlp = None  # fallback si no está disponible por algún motivo

# Cargar configuración NLP desde JSON
import json as _json_nlp
from pathlib import Path as _Path_nlp

def _load_nlp_config():
    """Carga configuración NLP desde JSON."""
    json_path = _Path_nlp(__file__).resolve().parents[3] / "shared" / "system_nlp_config.json"
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return _json_nlp.load(f)
    except Exception as e:
        log_error(f"No se pudo cargar system_nlp_config.json: {e}")
        return {
            'fashion_categories': [],
            'fashion_terms': ['short','shorts','top','crop','leggins','jeggings','blazer'],
            'color_adjectives': ['chocolate'],
            'semantic_color_config': {}
        }

_NLP_CONFIG = _load_nlp_config()

# Sistema de módulos personalizados por cliente
from app.search_modules import get_client_module, has_custom_module
from app.utils.llm_query_normalizer import extract_query_attributes

bp = Blueprint("search_text", __name__)

# Habilitar CORS
CORS(bp, origins=["*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "X-API-Key"])


# --- Preprocesamiento de consulta (spaCy) ---
_NLP_ES_WITH_PARSER = None  # Instancia con parser habilitado para análisis de dependencias

def _get_nlp_es():
    """Obtiene el modelo spaCy español CON parser habilitado.

    IMPORTANTE: No reutiliza _get_spacy_nlp del blueprint API porque ese
    deshabilita el parser para reducir overhead. Esta función necesita
    el parser para análisis de dependencias.
    """
    global _NLP_ES_WITH_PARSER
    if _NLP_ES_WITH_PARSER is not None:
        return _NLP_ES_WITH_PARSER

    try:
        import spacy  # type: ignore
        # Permitir configurar el modelo por ENV; default a 'es_core_news_md'
        model_name = os.getenv("SPACY_MODEL", "es_core_news_md")
        # Cargar con parser habilitado (solo deshabilitar NER y textcat para reducir overhead)
        _NLP_ES_WITH_PARSER = spacy.load(model_name, disable=["ner", "textcat"])

        # Agregar AttributeRuler para categorías de moda (forzar POS=NOUN)
        if "attribute_ruler_fashion" not in _NLP_ES_WITH_PARSER.pipe_names:
            ruler = _NLP_ES_WITH_PARSER.add_pipe("attribute_ruler", name="attribute_ruler_fashion", before="parser")

            # Cargar categorías desde JSON
            FASHION_CATEGORIES = _NLP_CONFIG.get('fashion_categories', [])

            patterns = [{"patterns": [[{"LOWER": term}]], "attrs": {"POS": "NOUN"}}
                        for term in FASHION_CATEGORIES]
            ruler.add_patterns(patterns)
            log_nlp(f"AttributeRuler fashion agregado ({len(FASHION_CATEGORIES)} términos)")

        # Segundo AttributeRuler: forzar ciertos términos a ADJETIVOS (colores descriptivos)
        # Objetivo: permitir que 'chocolate' NO sea interpretado como categoría principal
        # en queries como "delantal chocolate" y pase al pipeline semántico de color.
        if "attribute_ruler_semantic_colors" not in _NLP_ES_WITH_PARSER.pipe_names:
            ruler_colors = _NLP_ES_WITH_PARSER.add_pipe(
                "attribute_ruler",
                name="attribute_ruler_semantic_colors",
                before="parser"
            )
            # Cargar adjetivos de color desde JSON
            COLOR_ADJECTIVES = _NLP_CONFIG.get('color_adjectives', [])
            color_patterns = [
                {"patterns": [[{"LOWER": term}]], "attrs": {"POS": "ADJ"}}
                for term in COLOR_ADJECTIVES
            ]
            ruler_colors.add_patterns(color_patterns)
            log_nlp(f"AttributeRuler color-adj agregado ({len(COLOR_ADJECTIVES)} términos)")

        return _NLP_ES_WITH_PARSER
    except Exception as e:
        log_error(f"No se pudo cargar spaCy con parser: {e}")
        return None


def _generate_attribute_prompts(modificador: str, categoria: str = None, variants: list = None) -> list:
    """Genera prompts dinámicos para inferir un atributo desde CLIP.

    Args:
        modificador: El atributo a buscar (ej: "negra", "brillante", "algodón")
        categoria: Categoría del producto (ej: "remera", "pantalón")
        variants: Variantes del modificador (ej: ["negro", "dark"])

    Returns:
        Lista de prompts en español e inglés
    """
    prompts = []

    # Variantes del modificador a probar
    mod_variants = [modificador]
    if variants:
        mod_variants.extend(variants)
    mod_variants = list(set(mod_variants))  # Eliminar duplicados

    for mod in mod_variants:
        # Prompts en español e inglés para cubrir descripciones libres
        prompts.append(f"{mod}")  # Solo el modificador
        prompts.append(f"a {mod}")  # Inglés genérico
        if categoria:
            prompts.append(f"{categoria} {mod}")  # "remera negra"
            prompts.append(f"{mod} {categoria}")  # "negra remera"
            prompts.append(f"a {mod} {categoria}")  # "a black t-shirt"
            prompts.append(f"{categoria} with {mod}")  # "t-shirt with pockets"

    return prompts


# 🚀 CACHE global para embeddings de prompts (optimización crítica)
_prompt_embeddings_cache = {}  # {prompt_key: np.ndarray}
_clip_cache_lock = None

def _get_prompt_embeddings_cached(prompts: list, categoria: str = None) -> np.ndarray:
    """Cachea embeddings de prompts para evitar recalcularlos 100+ veces.

    OPTIMIZACIÓN CRÍTICA: Esto reduce 2+ minutos a <100ms

    Args:
        prompts: Lista de strings a embedder
        categoria: Categoría (usada solo para logging)

    Returns:
        np.ndarray de embeddings (n_prompts, 512)
    """
    # Crear clave única para este conjunto de prompts
    prompt_key = tuple(sorted(prompts))

    # Si ya está cacheado, devolverlo
    if prompt_key in _prompt_embeddings_cache:
        return _prompt_embeddings_cache[prompt_key]

    # Si no, generar embedding UNA SOLA VEZ
    try:
        clip_model, clip_processor = get_clip_model()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        with torch.no_grad():
            text_inputs = clip_processor(
                text=prompts,
                return_tensors="pt",
                padding=True
            ).to(device)
            prompt_embeddings = clip_model.get_text_features(**text_inputs)
            prompt_embeddings = prompt_embeddings / prompt_embeddings.norm(dim=-1, keepdim=True)

        # Guardar en cache
        embeddings_np = prompt_embeddings.cpu().numpy()
        _prompt_embeddings_cache[prompt_key] = embeddings_np

        if len(_prompt_embeddings_cache) % 5 == 0:
            log_verbose(f"📊 Prompt embeddings cache size: {len(_prompt_embeddings_cache)}")

        return embeddings_np
    except Exception as e:
        log_error(f"Error generating cached prompt embeddings: {e}")
        return np.array([])


def _infer_attribute_from_clip_cached(image_vec: np.ndarray, modificador: str, categoria: str = None,
                                      variants: list = None, threshold: float = 0.20) -> dict:
    """Infiere atributo usando CLIP con embeddings de prompts cacheados.

    OPTIMIZACIÓN: Cachea embeddings de prompts (operación lenta) para reutilizarlos.
    Reduce tiempo de 2+ minutos a <100ms.

    Args:
        image_vec: Vector embedding de la imagen
        modificador: Atributo a buscar
        categoria: Categoría del producto (mejora contexto)
        variants: Variantes del modificador
        threshold: Umbral para confianza (high/medium/low)

    Returns:
        Dict con similitudes y confianza
    """
    try:
        # Generar prompts
        prompts = _generate_attribute_prompts(modificador, categoria, variants)

        # Obtener embeddings (cacheados o nuevos)
        prompt_embeddings = _get_prompt_embeddings_cached(prompts, categoria)

        if len(prompt_embeddings) == 0:
            return {
                'has_attribute': False,
                'max_similarity': 0.0,
                'confidence': 'error'
            }

        # Comparar contra imagen (operación MUY rápida)
        similarities = [float(np.dot(image_vec, pv)) for pv in prompt_embeddings]
        max_sim = max(similarities) if similarities else 0.0

        # Determinar confianza
        if max_sim >= 0.65:
            confidence = 'high'
            has_attr = True
        elif max_sim >= threshold:
            confidence = 'medium'
            has_attr = True
        else:
            confidence = 'low'
            has_attr = False

        return {
            'has_attribute': has_attr,
            'max_similarity': max_sim,
            'confidence': confidence,
            'all_similarities': similarities
        }
    except Exception as e:
        log_error(f"Error inferring attribute '{modificador}' from CLIP: {e}")
        return {
            'has_attribute': False,
            'max_similarity': 0.0,
            'confidence': 'error'
        }


## Eliminado: función deprecada _infer_attribute_from_clip


def _extract_key_terms_with_dependency_parsing(text: str, client_profile: dict = None) -> dict:
    """Extrae términos clave con análisis de dependencias.

    Args:
        text: Query del usuario
        client_profile: Perfil de búsqueda del cliente (opcional)
    """
    # EXTRACTOR V2 - reglas de profundidad estrictas + ignora verbos
    nlp = _get_nlp_es()
    if nlp is None:
        return {'text': text.lower(), 'category': None, 'modifiers': [], 'success': False}

    doc = nlp(text)
    principal = None
    categoria_principal = None
    modificadores = []
    elementos_extraidos = set()
    verb_tokens = {t for t in doc if t.pos_ == 'VERB'}

    # Cargar fashion terms y categories desde JSON
    FASHION_TERMS = set(_NLP_CONFIG.get('fashion_terms', []))
    FASHION_CATEGORIES_SET = set(_NLP_CONFIG.get('fashion_categories', []))

    # Obtener variants_map del perfil si existe
    variants_map = client_profile.get('variants_map', {}) if client_profile else {}

    def _to_singular(token, variants_map=None):
        """Normaliza token usando lemma de spaCy + variants_map opcional del perfil."""
        txt = token.text.lower()
        lemma = token.lemma_.lower()

        # 1. Si está en variants_map del perfil, usar ese mapeo
        if variants_map and txt in variants_map:
            return variants_map[txt]

        # 2. Fallback a lógica original
        if txt in FASHION_TERMS:
            if txt.endswith('s') and len(txt) > 3:
                return txt[:-1]
            return txt
        return token.lemma_.lower()

    # ESTRATEGIA MEJORADA: Recolectar TODOS los NOUN candidatos en un solo pase
    # Priorizar los que están en fashion_categories, independientemente de su dependencia
    candidates = []
    for token in doc:
        if not token.is_alpha or token.is_stop or token.pos_ == 'VERB':
            continue

        # Evaluar si es un candidato válido (NOUN o fashion term)
        tl = token.text.lower()
        is_noun_candidate = (token.pos_ in ('NOUN','PROPN')) or (tl in FASHION_TERMS)

        if is_noun_candidate:
            term = _to_singular(token, variants_map)
            if term and len(term) >= 3:
                in_categories = term in FASHION_CATEGORIES_SET
                # Prioridad: dep relevante = 0, otros = 1
                priority = 0 if token.dep_ in ('ROOT','obj','nsubj','dobj') else 1
                candidates.append((token, term, in_categories, priority))

    # Ordenar por: 1) en fashion_categories (True primero), 2) prioridad dep, 3) posición
    if candidates:
        candidates.sort(key=lambda x: (not x[2], x[3], x[0].i))
        principal = candidates[0][0]
        categoria_principal = candidates[0][1]
        elementos_extraidos.add(categoria_principal)
        if candidates[0][2]:
            log_verbose(LogCategory.NLP, f"Principal seleccionado (en vocabulario): '{categoria_principal}' (dep={principal.dep_})")
        else:
            log_verbose(LogCategory.NLP, f"Principal seleccionado (fuera de vocabulario): '{categoria_principal}' (dep={principal.dep_})")

    if not principal:
        log_verbose(LogCategory.NLP, "No se detectó sustantivo principal")
        return {'text':'','category':None,'modifiers':[],'success':False}    # Ya no necesitamos la promoción post-hoc porque priorizamos en la selección inicial
    log_verbose(LogCategory.NLP, f"[NIVEL 1] Buscando modificadores directos de '{principal.text}'")

    nivel2_discarded = set()  # Rastrear términos descartados por ser nivel 2

    # CRÍTICO: Si el principal es hijo de un verbo ignorado, procesar también hermanos
    # Caso: "muestrame [delantales] con [cierre]" → cierre es hermano de delantales, no hijo
    nodes_to_process = list(principal.children)  # Hijos directos del principal

    if principal.head.pos_ == 'VERB' and principal.head in verb_tokens:
        # El principal depende de un verbo ignorado: procesar sus hermanos también
        for sibling in principal.head.children:
            if sibling == principal:
                continue  # No procesar el principal de nuevo
            if not sibling.is_alpha or sibling.is_stop or sibling.pos_ == 'VERB':
                continue
            # Solo agregar hermanos que sean sustantivos o preposiciones (estructuras relacionadas)
            if sibling.pos_ in ('NOUN', 'PROPN') or sibling.dep_ in ('obl', 'prep', 'nmod'):
                nodes_to_process.append(sibling)
                print(f"  🔗 Procesando hermano del principal: '{sibling.text}' (DEP={sibling.dep_}, POS={sibling.pos_})")
                # 🔍 DEBUG: Mostrar hijos del hermano
                log_verbose(LogCategory.NLP, f"     Hijos de '{sibling.text}': {[(c.text, c.dep_, c.pos_) for c in sibling.children]}")

    for child in nodes_to_process:
        if not child.is_alpha or child.is_stop or child.pos_ == 'VERB':
            continue

        # CASO 0: Sustantivo hermano del principal (obl, nmod directo) → CAPTURAR como nivel 1
        # Ejemplo: "muestrame delantales con cierre" → cierre es obl de muestrame (hermano de delantales)
        if child.dep_ in ('obl', 'nmod') and child.pos_ in ('NOUN', 'PROPN'):
            term = _to_singular(child, variants_map)
            if term and len(term) >= 3:
                elementos_extraidos.add(term)
                modificadores.append(term)
                log_verbose(LogCategory.NLP, f"  ✅ Sustantivo nivel 1 (hermano): '{term}' (original: '{child.text}', dep={child.dep_})")

                # FUNCIÓN RECURSIVA: Buscar coordinaciones en TODA la subrama
                # Ejemplo: "con cierre al costado y bolsillos grandes"
                # → cierre (nivel 1) → costado (nivel 2) → bolsillos (conj de costado)
                def find_coordinations(node, base_term, current_depth=2):
                    # Busca recursivamente coordinaciones (conj) en toda la subrama.
                    for child_node in node.children:
                        # Coordinación encontrada: capturar como nivel 1
                        if child_node.dep_ == 'conj' and child_node.pos_ in ('NOUN', 'PROPN'):
                            coord_term = _to_singular(child_node, variants_map)
                            if coord_term and len(coord_term) >= 3:
                                elementos_extraidos.add(coord_term)
                                modificadores.append(coord_term)
                                log_verbose(LogCategory.NLP, f"  ✅ Sustantivo nivel 1 (coordinado con '{base_term}' via nivel {current_depth}): '{coord_term}' (original: '{child_node.text}')")

                                # Marcar SUS hijos como descartados
                                for gcc in child_node.children:
                                    if gcc.is_alpha and not gcc.is_stop and gcc.dep_ not in ('case', 'cc', 'conj'):
                                        coord_child_term = _to_singular(gcc, variants_map)
                                        nivel2_discarded.add(coord_child_term)

                                # Continuar buscando coordinaciones más profundas
                                find_coordinations(child_node, coord_term, current_depth + 1)

                        # Seguir explorando la subrama (sin capturar nada más)
                        elif child_node.dep_ not in ('case', 'cc'):
                            find_coordinations(child_node, base_term, current_depth + 1)

                # Buscar coordinaciones en toda la subrama del hermano
                find_coordinations(child, term, current_depth=2)

                # ⚠️ SUS HIJOS SON NIVEL 2 → DESCARTAR (excepto coordinaciones ya procesadas)
                nivel2_terms = []
                for gc in child.children:
                    if not gc.is_alpha or gc.is_stop:
                        continue
                    # Saltar case markers (con, al, de, etc.), conjunciones coordinantes (y, o) y coordinaciones (procesadas arriba)
                    if gc.dep_ in ('case', 'cc', 'conj'):
                        continue

                    nivel2_term = _to_singular(gc, variants_map)
                    nivel2_discarded.add(nivel2_term)
                    nivel2_terms.append(gc.text)

                    # Descartar TODA la cadena anidada (excepto coordinaciones)
                    def discard_chain(node):
                        for ggc in node.children:
                            if ggc.is_alpha and not ggc.is_stop and ggc.dep_ not in ('case', 'cc', 'conj'):
                                chain_term = _to_singular(ggc, variants_map)
                                nivel2_discarded.add(chain_term)
                                nivel2_terms.append(ggc.text)
                                discard_chain(ggc)  # Continuar recursivamente

                    discard_chain(gc)

                if nivel2_terms:
                    log_verbose(LogCategory.NLP, f"    ⛔ Descartando {len(nivel2_terms)} modificadores nivel 2+ de '{term}': {nivel2_terms}")
                continue

        # CASO 1: Adjetivo directo (amod) → CAPTURAR
        if child.dep_ == 'amod' and child.pos_ == 'ADJ':
            term = _to_singular(child, variants_map)
            if term and len(term) >= 3:
                elementos_extraidos.add(term)
                modificadores.append(term)
                log_verbose(LogCategory.NLP, f"  ✅ Adjetivo nivel 1: '{term}' (original: '{child.text}', amod)")

        # CASO 2: Sustantivo relacionado directo (nmod, pobj, compound) → CAPTURAR
        elif child.dep_ in ('nmod', 'pobj', 'compound') and child.pos_ in ('NOUN', 'PROPN'):
            term = _to_singular(child, variants_map)
            if term and len(term) >= 3:
                elementos_extraidos.add(term)
                modificadores.append(term)
                log_verbose(LogCategory.NLP, f"  ✅ Sustantivo nivel 1: '{term}' (original: '{child.text}', dep={child.dep_})")

                # ⚠️ Contar pero NO capturar hijos (nivel 2)
                nivel2_terms = [gc.text for gc in child.children if gc.is_alpha and not gc.is_stop]
                if nivel2_terms:
                    # Marcar como descartados para evitar fallback
                    for gc in child.children:
                        if gc.is_alpha and not gc.is_stop:
                            nivel2_term = _to_singular(gc, variants_map)
                            nivel2_discarded.add(nivel2_term)
                    log_verbose(LogCategory.NLP, f"    ⛔ Descartando {len(nivel2_terms)} modificadores nivel 2 de '{term}': {nivel2_terms}")        # CASO 3: Preposiciones (prep) → buscar pobj dentro
        elif child.dep_ == 'prep':
            for prep_child in child.children:
                if not prep_child.is_alpha or prep_child.is_stop or prep_child.pos_ == 'VERB':
                    continue
                if prep_child.dep_ == 'pobj' and prep_child.pos_ in ('NOUN', 'PROPN'):
                    term = _to_singular(prep_child, variants_map)
                    if term and len(term) >= 3:
                        elementos_extraidos.add(term)
                        modificadores.append(term)
                        log_verbose(LogCategory.NLP, f"  ✅ Sustantivo nivel 1 (via prep '{child.text}'): '{term}' (original: '{prep_child.text}')")

                        # ⚠️ Contar pero NO capturar hijos (nivel 2)
                        nivel2_terms = [gc.text for gc in prep_child.children if gc.is_alpha and not gc.is_stop]
                        if nivel2_terms:
                            # Marcar como descartados para evitar fallback
                            for gc in prep_child.children:
                                if gc.is_alpha and not gc.is_stop:
                                    nivel2_term = _to_singular(gc, variants_map)
                                    nivel2_discarded.add(nivel2_term)

                                # CRÍTICO: Si el hijo es otra preposición, descartar TODA la cadena
                                if gc.dep_ == 'prep':
                                    for prep_grandchild in gc.children:
                                        if prep_grandchild.is_alpha and not prep_grandchild.is_stop:
                                            nivel2_gc_term = _to_singular(prep_grandchild, variants_map)
                                            nivel2_discarded.add(nivel2_gc_term)

                            log_verbose(LogCategory.NLP, f"    ⛔ Descartando {len(nivel2_terms)} modificadores nivel 2 de '{term}': {nivel2_terms}")

    # === PASO 3: Fallback para términos mal etiquetados ===
    # Incluir también colores semánticos del diccionario sistémico
    # aunque no vengan etiquetados como NOUN/PROPN (ej: "chocolate").
    semantic_color_tokens = set()
    try:
        from app.utils.semantic_colors import get_system_color_adjectives
        semantic_color_tokens = {
            str(c).strip().lower()
            for c in get_system_color_adjectives()
            if str(c).strip()
        }
    except Exception:
        semantic_color_tokens = set()

    fallback_added = []
    processed_lemmas = {e.lower() for e in elementos_extraidos}
    processed_lemmas.update(nivel2_discarded)  # Excluir términos nivel 2 del fallback

    for token in doc:
        if not token.is_alpha or token.is_stop or token.pos_ == 'VERB':
            continue
        token_lower = token.text.lower()
        is_fashion_or_noun = token.pos_ in ('NOUN', 'PROPN') or token_lower in FASHION_TERMS
        is_semantic_color = token_lower in semantic_color_tokens

        if not is_fashion_or_noun and not is_semantic_color:
            continue

        term = _to_singular(token, variants_map)
        if term and len(term) >= 3 and term not in processed_lemmas:
            elementos_extraidos.add(term)
            modificadores.append(term)
            fallback_added.append(f"{term} (original: '{token.text}')")

    if fallback_added:
        log_verbose(LogCategory.NLP, f"[FALLBACK] Capturados por mistagging: {fallback_added}")

    # === RESULTADO FINAL ===
    if not elementos_extraidos:
        log_verbose(LogCategory.NLP, f"[EXTRACTOR] No se capturó ningún término relevante")
        log_verbose(LogCategory.NLP, "=" * 60 + "\n")
        return {
            'text': '',
            'category': categoria_principal,
            'modifiers': modificadores,
            'success': False
        }

    resultado = " ".join(sorted(list(elementos_extraidos)))
    log_verbose(LogCategory.NLP, f"[RESULTADO] {len(elementos_extraidos)} términos: {sorted(list(elementos_extraidos))}")
    log_verbose(LogCategory.NLP, f"📦 [CATEGORÍA] '{categoria_principal}'")
    log_verbose(LogCategory.NLP, f"🏷️  [MODIFICADORES] {modificadores if modificadores else '(ninguno)'}")
    log_verbose(LogCategory.NLP, f"✅ [SALIDA] '{resultado}'")
    log_verbose(LogCategory.NLP, "=" * 60 + "\n")

    return {
        'text': resultado,
        'category': categoria_principal,
        'modifiers': modificadores,
        'success': True
    }


def _build_user_feedback(query_text: str, formatted_results: list, detected_category_info: dict = None,
                        client_id: str = None, attrs_requested: dict = None, contradictions: list = None,
                        not_configured: list = None, all_available_values: dict = None,
                        detected_color_token: str = None, detected_color_normalized: str = None):
    # Feedback dinámico para el usuario (categoría, color, atributos, contradicciones)
    from app.utils.colors import normalize_color  # import interno para evitar dependencias circulares

    # Extraer colores disponibles en resultados (normalizados)
    available_colors = []
    for r in formatted_results:
        color_val = (r.get('attributes') or {}).get('color')
        if color_val:
            norm_col = normalize_color(color_val.lower(), client_id=client_id) or color_val.lower()
            if norm_col not in available_colors:
                available_colors.append(norm_col)

    shown_categories = []
    for r in formatted_results:
        cat = r.get('category')
        if cat and cat not in shown_categories:
            shown_categories.append(cat)

    parts = []

    # Categoría - usar SOLO las categorías que realmente aparecen en los resultados
    if detected_category_info:
        req_term = detected_category_info.get('requested_term')
        matched_categories = detected_category_info.get('matched_categories', [])
        if req_term and matched_categories:
            # Solo si hubo reinterpretación
            if req_term.lower() not in [c.lower() for c in matched_categories]:
                # Usar shown_categories (categorías reales en resultados) en lugar de matched_categories
                if shown_categories:
                    if len(shown_categories) == 1:
                        cat_text = shown_categories[0]
                    elif len(shown_categories) == 2:
                        cat_text = f"{shown_categories[0]} y {shown_categories[1]}"
                    else:
                        cat_text = f"{', '.join(shown_categories[:-1])} y {shown_categories[-1]}"
                    parts.append(f"Buscaste '{req_term}', mostrando resultados de {cat_text}")

    # Atributos solicitados - mostrar valores disponibles (EXCEPTO color, que tiene lógica especial)
    if attrs_requested and all_available_values:
        # Cargar mapa key -> etiqueta
        label_map = {}
        if client_id:
            try:
                from app.models.product_attribute_config import ProductAttributeConfig
                cfgs = ProductAttributeConfig.query.filter_by(client_id=client_id).all()
                for c in cfgs:
                    k = (c.key or '').strip().lower()
                    if not k:
                        continue
                    label_map[k] = (c.label or k)
            except Exception:
                label_map = {}

        import unicodedata as _ud
        def _norm(x):
            if x is None:
                return ''
            txt = str(x).strip().lower()
            txt = ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')
            if txt in ('si','sí'):
                return 'si'
            return txt
        def _fmt_val(x):
            n = _norm(x)
            if n == 'si':
                return 'Sí'
            if n == 'no':
                return 'No'
            return str(x).upper()

        for attr_key, attr_value in attrs_requested.items():
            # Saltar 'color': tiene lógica especial más abajo
            if str(attr_key).lower() == 'color':
                continue

            available_vals = all_available_values.get(attr_key, [])
            if not available_vals:
                continue

            # Mostrar etiqueta si existe
            display_key = label_map.get(attr_key, attr_key)

            # Comparación acento-insensible y unificada para sí/no
            req_norm = _norm(attr_value)
            avail_norm = [_norm(v) for v in available_vals]

            if req_norm and req_norm in avail_norm:
                # Valor solicitado está disponible → listar disponibles (formateados)
                parts.append(f"Tenemos disponibles en {display_key}: {', '.join(_fmt_val(v) for v in available_vals)}")
            else:
                parts.append(
                    f"No disponemos en {display_key}: '{_fmt_val(attr_value)}'. "
                    f"Tenemos disponibles en {display_key}: {', '.join(_fmt_val(v) for v in available_vals)}"
                )

    # Atributos no configurados
    if not_configured:
        attrs_str = ', '.join([f"'{a}'" for a in not_configured])
        if len(not_configured) == 1:
            parts.append(f"El atributo {attrs_str} no está configurado para este catálogo")
        else:
            parts.append(f"Los atributos {attrs_str} no están configurados para este catálogo")

    # Banner inteligente de color solicitado
    try:
        if detected_color_token:
            # Solo informar interpretación si hubo mapeo REAL (token ambiguo → color claro)
            # No mostrar si el color ya venía de atributos o si el token ES el color normalizado
            if detected_color_normalized and detected_color_token.lower() != detected_color_normalized.lower():
                # Verificar que no sea un caso donde el atributo 'color' ya estaba en attrs_requested
                # (evita decir "Interpretamos X como Y" cuando Y ya venía explícito)
                show_interpretation = True
                if attrs_requested and 'color' in attrs_requested:
                    # Si el color solicitado en attrs coincide con detected_normalized, no mostrar
                    if str(attrs_requested['color']).lower() == detected_color_normalized.lower():
                        show_interpretation = False

                if show_interpretation:
                    parts.append(f"Interpretamos '{detected_color_token}' como color '{detected_color_normalized}'")

            # Si hay resultados, mostrar también otros colores disponibles
            if formatted_results and available_colors:
                # Quitar el color actual de la lista de "también disponibles"
                other_colors = [c for c in available_colors if c != detected_color_normalized]
                if other_colors and all_available_values and 'color' in all_available_values:
                    # Usar todos los colores de la categoría (antes del filtrado)
                    all_colors_in_category = []
                    for c in all_available_values['color']:
                        normalized = normalize_color(c.lower(), client_id=client_id) or c.lower()
                        if normalized != detected_color_normalized and normalized not in all_colors_in_category:
                            all_colors_in_category.append(normalized)

                    if all_colors_in_category:
                        parts.append(f"También tenemos disponible en: {', '.join(sorted(all_colors_in_category))}")

            elif not formatted_results:
                # No hay resultados: listar todos los colores disponibles en la categoría
                if all_available_values and 'color' in all_available_values:
                    all_colors_in_category = []
                    for c in all_available_values['color']:
                        normalized = normalize_color(c.lower(), client_id=client_id) or c.lower()
                        if normalized not in all_colors_in_category:
                            all_colors_in_category.append(normalized)

                    if all_colors_in_category:
                        cat_for_msg = shown_categories[0] if shown_categories else 'productos'
                        parts.append(
                            f"No tenemos {cat_for_msg} disponible en color '{detected_color_normalized}'. "
                            f"Tenemos disponible en: {', '.join(sorted(all_colors_in_category))}"
                        )
    except Exception as e:
        log_error(f"Error construyendo feedback de color: {e}")

    # Contradicciones
    if contradictions:
        parts.append(f"Tu búsqueda contiene criterios contradictorios: {', '.join(contradictions)}")

    # Final
    if not parts:
        if len(shown_categories) == 1:
            parts.append(f"Mostrando {len(formatted_results)} resultados en '{shown_categories[0]}'")
        else:
            parts.append(f"Encontramos {len(formatted_results)} productos para tu búsqueda")

    message = '. '.join(parts) + '.'
    return {
        'message': message,
        'has_results': bool(formatted_results),
        'result_count': len(formatted_results),
        'categories_shown': shown_categories,
        'colors_available': available_colors or None,
        'requested_color': detected_color_normalized,
        'attributes_requested': attrs_requested or {},
        'attributes_not_configured': not_configured or [],
        'contradictions': contradictions or []
    }


def verify_api_key():
    # Valida API Key del request
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None, "API Key requerida"

    client = Client.query.filter_by(api_key=api_key).first()
    if not client:
        return None, "API Key inválida"

    return client, None


def expand_query_with_synonyms(query_text: str, client_id: str, client_slug: str = None):
    """
    Expande query con sinónimos usando el nuevo proveedor de perfiles de búsqueda.

    Prioridad:
    1. Perfil del cliente (por industria + overrides)
    2. Módulo custom si existe (para compatibilidad)
    3. Fallback genérico
    """
    try:
        # 🆕 Intentar usar proveedor de perfiles
        profile = SearchProfilesService.get_profile(client_id)
        categories = Category.query.filter_by(client_id=client_id).all()
        result = SearchProfilesService.expand_query(query_text, categories, profile)
        log_verbose(LogCategory.SEARCH, f"[Perfil de Búsqueda] Expansión: {len(result)} términos")
        return result
    except Exception as e:
        log_verbose(LogCategory.SEARCH, f"[Perfil] Error, intentando fallback: {e}")

    # Fallback: módulo custom si existe
    if client_slug and has_custom_module(client_slug):
        module = get_client_module(client_slug)
        try:
            categories = Category.query.filter_by(client_id=client_id).all()
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            log_error(f"[Módulo Custom] Error consultando categorías: {e}")
            return query_text.lower().split()
        result = module.expand_query(query_text, categories)
        log_verbose(LogCategory.SEARCH, f"[Módulo Custom] Expansión: {len(result)} términos")
        return result

    # Fallback genérico
    tokens = query_text.lower().split()
    expanded = set(tokens)

    try:
        categories = Category.query.filter_by(client_id=client_id).all()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        log_error(f"[Genérico] Error obteniendo categorías: {e}")
        return list(expanded)

    for cat in categories:
        if not cat.alternative_terms:
            continue
        cat_synonyms = [s.strip() for s in cat.alternative_terms.split(',')]
        for token in tokens:
            if token in cat_synonyms:
                expanded.update(cat_synonyms)
                break

    result = list(expanded)
    log_verbose(LogCategory.NLP, f"[Genérico] Query expandido: {len(result)} términos")
    return result

    result = list(expanded)
    log_verbose(LogCategory.NLP, f"[Genérico] Query expandido: '{query_text}' → {len(result)} términos: {result[:10]}...")
    return result


def _normalize_tokens_es(text: str) -> List[str]:
    # Tokeniza y lematiza en español (spaCy si disponible); fallback: split básico
    if not text:
        return []

    # Mapa mínimo de variantes comunes del dominio textil
    variants_map = {
        "shorts": "short",
        "shores": "short",
        "remeras": "remera",
        "pantalones": "pantalon",
        "gorras": "gorra",
        "gorros": "gorro",
    }

    try:
        if _get_spacy_nlp:
            nlp = _get_spacy_nlp()
        else:
            nlp = None
        if nlp is not None:
            doc = nlp(text.lower())
            toks = []
            for t in doc:
                if not t.is_alpha or t.is_stop:
                    continue
                lemma = t.lemma_.strip().lower()
                lemma = variants_map.get(lemma, lemma)
                if lemma:
                    toks.append(lemma)
            return toks
    except Exception:
        # Fallback simple si spaCy falla
        pass

    # Fallback: dividir por espacios + normalización mínima
    toks = []
    for raw in text.lower().replace('-', ' ').split():
        tok = variants_map.get(raw, raw)
        # Singularizar simple: quitar sufijo 's' si aplica (no agresivo)
        if tok.endswith('s') and len(tok) > 3:
            tok = tok[:-1]
        if tok.isalpha():
            toks.append(tok)
    return toks


def _category_tokens(cat: Category) -> Set[str]:
    # Construye set de tokens normalizados (name, name_en, alternative_terms)
    tokens: Set[str] = set()
    # name y name_en
    if getattr(cat, 'name', None):
        tokens.update(_normalize_tokens_es(cat.name))
    if getattr(cat, 'name_en', None):
        tokens.update(_normalize_tokens_es(cat.name_en))
    # alternative_terms (coma separada, puede contener frases)
    if getattr(cat, 'alternative_terms', None):
        for term in [s.strip() for s in cat.alternative_terms.split(',') if s.strip()]:
            tokens.update(_normalize_tokens_es(term))
    return {t for t in tokens if t}


_CLIENT_CATEGORY_TOKENS_CACHE = {}


def _get_client_category_tokens_for_clip(client_id: str) -> Set[str]:
    cache_key = str(client_id)
    if cache_key in _CLIENT_CATEGORY_TOKENS_CACHE:
        return set(_CLIENT_CATEGORY_TOKENS_CACHE[cache_key])

    tokens: Set[str] = set()
    try:
        categories = Category.query.filter_by(client_id=client_id, is_active=True).all()
        for category in categories:
            tokens.update(_category_tokens(category))
    except Exception:
        return set()

    _CLIENT_CATEGORY_TOKENS_CACHE[cache_key] = tuple(sorted(tokens))
    return set(tokens)


def stage1_broad_recall(query_text: str, client_id: str, client_slug: str = None, is_color_search: bool = False):
    # STAGE 1: Broad Recall - PostgreSQL SIMILAR TO (sin docstring multiline para evitar errores)
    # 🔧 Ahora recibimos is_color_search para saber si debe traer TODOS los productos de categoría
    start_time = time.time()

    def _hang_trace(msg: str):
        return None

    # 1️⃣ Expandir query con sinónimos (ahora usa proveedor de perfiles)
    expanded_tokens = expand_query_with_synonyms(query_text, client_id, client_slug)

    # 1.1 Detectar categorías para filtrar (usa proveedor de perfiles)
    categories = Category.query.filter_by(client_id=client_id).all()
    category_filter_ids = []
    detection_metadata = None
    has_valid_category = False  # 🆕 Bandera: ¿tenemos categoría detectada válida?

    try:
        # 🆕 Usar proveedor de perfiles de búsqueda
        client = Client.query.get(client_id)
        profile = SearchProfilesService.get_profile(client_id, client.industry if client else None)

        # Normalizar tokens usando el perfil
        query_tokens = SearchProfilesService.normalize_tokens(query_text, profile)

        # Detectar filtro de categoría
        category_filter_ids, detection_metadata = SearchProfilesService.detect_category_filter(
            query_tokens, categories, profile
        )

        if category_filter_ids:
            has_valid_category = True
            log_verbose(LogCategory.SEARCH, f"[Perfil de Búsqueda] Filtro de categoría: {len(category_filter_ids)} categorías detectadas")
        else:
            log_verbose(LogCategory.SEARCH, f"[Perfil de Búsqueda] Sin filtro de categoría (búsqueda amplia)")
    except Exception as e:
        log_verbose(LogCategory.SEARCH, f"[Perfil] Error detectando categoría, intentando fallback: {e}")

        # Fallback: módulo custom si existe
        if client_slug and has_custom_module(client_slug):
            module = get_client_module(client_slug)
            query_tokens = module.normalize_tokens(query_text)
            result = module.detect_category_filter(query_tokens, categories)
            if isinstance(result, tuple):
                category_filter_ids, detection_metadata = result
            else:
                category_filter_ids = result
                detection_metadata = None
        else:
            # Fallback genérico - ahora usa get_system_color_adjectives()
            try:
                from app.utils.semantic_colors import get_system_color_adjectives
                system_colors = {str(c).strip().lower() for c in get_system_color_adjectives() if c}
            except Exception:
                system_colors = {"rojo", "verde", "azul", "negro", "blanco", "marron", "gris", "beige", "rosa", "amarillo", "violeta"}

            original_tokens = _normalize_tokens_es(query_text)
            filtered_query_tokens = [t for t in original_tokens if t not in system_colors]

            matched_by_name = []
            for cat in categories:
                tokens_cat = _category_tokens(cat)
                for qt in filtered_query_tokens:
                    if qt in tokens_cat:
                        matched_by_name.append((cat.id, qt))
                        break

            root_to_cats = {}
            for cid, root in matched_by_name:
                root_to_cats.setdefault(root, []).append(cid)

            if len(root_to_cats) == 1:
                sole_root = next(iter(root_to_cats.keys()))
                category_filter_ids = root_to_cats[sole_root]
                has_valid_category = True

    # Normalizar category_filter_ids para SQL
    if not category_filter_ids:
        category_filter_ids = []

    # 🔧 LÓGICA DE LÍMITE INTELIGENTE:
    # Si tenemos categoría detectada válida, traemos TODOS los productos de esa categoría
    # Si es búsqueda de color sin categoría válida, traemos más candidatos (500)
    # Si es búsqueda genérica, limitamos a 50
    if has_valid_category:
        sql_limit = 100000  # Traer TODOS (con límite de seguridad)
        print(f"✅ Categoría válida detectada: retriendo TODOS los productos de la categoría para luego filtrar por color")
    elif is_color_search:
        sql_limit = 500  # Color sin categoría: más candidatos
        print(f"🎨 Búsqueda por color sin categoría específica: traemos top {sql_limit}")
    else:
        sql_limit = 50  # Búsqueda genérica: limitado
        print(f"📎 Búsqueda genérica: traemos top {sql_limit}")

    # 2️⃣ Construir pattern para SIMILAR TO
    # SIMILAR TO usa regex-like: %(term1|term2|term3)%
    pattern = f"%({'|'.join(expanded_tokens)})%"

    # 3️⃣ Query SQL flexible
    sql_query_stage1 = (
        "SELECT DISTINCT p.id "
        "FROM products p "
        "JOIN categories c ON c.id = p.category_id "
        "WHERE p.client_id = :client_id "
        "AND p.is_active = TRUE "
        "AND ((:use_filter = FALSE) OR p.category_id = ANY(:category_ids)) "
        "AND ("
        "  :skip_pattern = TRUE "
        "  OR ("
        "    LOWER(p.name) SIMILAR TO :pattern "
        "    OR (p.attributes IS NOT NULL AND jsonb_typeof(p.attributes) = 'object' AND EXISTS ("
        "         SELECT 1 FROM jsonb_each_text(p.attributes) attr WHERE LOWER(attr.value) SIMILAR TO :pattern"
        "       )) "
        "    OR (LOWER(c.name) SIMILAR TO :pattern OR LOWER(c.name_en) SIMILAR TO :pattern OR LOWER(c.alternative_terms) SIMILAR TO :pattern) "
        "  )"
        ") "
        "LIMIT :limit"
    )
    sql = text(sql_query_stage1)

    product_ids = db.session.execute(sql, {
        "client_id": client_id,
        "pattern": pattern,
        "limit": sql_limit,
        "skip_pattern": has_valid_category,
        "use_filter": bool(category_filter_ids),
        "category_ids": category_filter_ids if category_filter_ids else [None]
    }).fetchall()

    # Cargar productos completos
    products = []
    for row in product_ids:
        product = Product.query.get(row[0])
        if product:
            products.append(product)

    elapsed = time.time() - start_time
    log_search(f"STAGE 1: {len(products)} candidatos en {elapsed:.3f}s")

    # Retornar también metadata de detección (si existe)
    return products, detection_metadata


def stage2_precise_rerank_legacy(query_text: str, candidates: list, limit: int = 10):
    # LEGACY: STAGE 2 previo (text-to-text). Se mantiene por compatibilidad.
    if not candidates:
        return []

    start_time = time.time()

    # 1️⃣ Obtener modelo CLIP
    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 2️⃣ Generar embedding del query
    query_prompt = f"a photo of {query_text}"

    with torch.no_grad():
        query_inputs = clip_processor(text=[query_prompt], return_tensors="pt", padding=True).to(device)
        query_embedding = clip_model.get_text_features(**query_inputs)
        query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
        query_vec = query_embedding.cpu().numpy()[0]

    # 3️⃣ Calcular similitud con TEXTO de cada producto (BATCH para performance en CPU)
    scored_candidates = []

    product_texts = []
    product_prompts = []
    for product in candidates:
        product_parts = [product.name]

        if product.attributes:
            for key in ['color', 'tipo', 'material', 'talla']:
                if key in product.attributes and product.attributes[key]:
                    product_parts.append(str(product.attributes[key]))

        if product.category:
            product_parts.append(product.category.name)
            if product.category.name_en:
                product_parts.append(product.category.name_en)

        product_text = " ".join(product_parts)
        product_texts.append(product_text)
        product_prompts.append(f"a photo of {product_text}")

    all_prod_vecs = []
    batch_size = 64
    with torch.no_grad():
        for i in range(0, len(product_prompts), batch_size):
            prompt_batch = product_prompts[i:i + batch_size]
            prod_inputs = clip_processor(text=prompt_batch, return_tensors="pt", padding=True).to(device)
            prod_embeddings = clip_model.get_text_features(**prod_inputs)
            prod_embeddings = prod_embeddings / prod_embeddings.norm(dim=-1, keepdim=True)
            all_prod_vecs.append(prod_embeddings.cpu().numpy())

    if all_prod_vecs:
        prod_matrix = np.vstack(all_prod_vecs)
    else:
        prod_matrix = np.array([])

    if len(prod_matrix) > 0:
        similarities = np.dot(prod_matrix, query_vec)
        for idx, product in enumerate(candidates):
            scored_candidates.append({
                'product': product,
                'similarity': float(similarities[idx]),
                'product_text': product_texts[idx]
            })

    # 4️⃣ Ordenar por similitud
    scored_candidates.sort(key=lambda x: x['similarity'], reverse=True)

    # 5️⃣ Limitar resultados
    top_results = scored_candidates[:limit]

    elapsed = time.time() - start_time
    log_search(f"STAGE 2: Top {len(top_results)} rerankeados en {elapsed:.3f}s")

    # Log top 3
    for i, result in enumerate(top_results[:3], 1):
        log_verbose(LogCategory.SEARCH, f"   {i}. {result['product'].name} (sim: {result['similarity']:.3f})")

    return top_results


def _build_clip_query_from_extraction(
    extraction_result: dict,
    client_id: str,
    detected_color_token: str = None,
    detected_color_normalized: str = None,
) -> str:
    """Construye frase CLIP nueva: sustantivo + modificadores directos.

    - Si encuentra color sistémico (ej. chocolate), lo transforma al preferido principal
      antes de generar embedding (ej. delantal chocolate -> delantal marron).
    - Si no hay categoría extraída, devuelve cadena vacía.
    """
    if not isinstance(extraction_result, dict):
        return ""

    category = str(extraction_result.get('category') or '').strip().lower()
    modifiers = extraction_result.get('modifiers') or []
    if not category:
        return ""

    client_category_tokens = _get_client_category_tokens_for_clip(client_id)
    normalized_category_tokens = set(_normalize_tokens_es(category)) if category else set()
    category_matches_client_vocab = (
        True if not client_category_tokens else bool(normalized_category_tokens & client_category_tokens)
    )

    if not category_matches_client_vocab:
        print(f"🧠 CLIP query: categoría descartada por no pertenecer al vocabulario del cliente: '{category}'")
        category = ""

    normalized_modifiers = []
    systemic_map = {}
    excluded_tokens = set()
    try:
        from app.utils.semantic_colors import _load_system_colors
        data_sc = _load_system_colors()
        entries = data_sc.get('colors', []) if isinstance(data_sc, dict) else []
        for item in entries:
            token = str(item.get('token', '')).strip().lower()
            if not token:
                continue
            preferred = [
                str(v).strip().lower()
                for v in (item.get('preferred_matches', []) or [])
                if str(v).strip()
            ]
            if preferred:
                systemic_map[token] = preferred[0]
        excluded_cfg = data_sc.get('excluded_tokens', {}) if isinstance(data_sc, dict) else {}
        if isinstance(excluded_cfg, dict):
            for key, values in excluded_cfg.items():
                if key in ('description', 'min_token_length', 'require_adj_pos'):
                    continue
                if isinstance(values, list):
                    excluded_tokens.update(
                        str(value).strip().lower()
                        for value in values
                        if str(value).strip()
                    )
    except Exception:
        systemic_map = {}
        excluded_tokens = set()

    for raw_mod in modifiers:
        mod = str(raw_mod or '').strip().lower()
        if not mod:
            continue
        if mod == 'color' or mod in excluded_tokens:
            continue
        mapped = systemic_map.get(mod, mod)
        if mapped != mod:
            print(f"🎨 Normalización sistémica pre-CLIP: '{mod}' -> '{mapped}'")
        normalized_modifiers.append(mapped)

    explicit_color = str(detected_color_token or detected_color_normalized or '').strip().lower()
    if explicit_color:
        explicit_color = systemic_map.get(explicit_color, explicit_color)
        if explicit_color not in normalized_modifiers:
            normalized_modifiers.append(explicit_color)

    # Si la categoría extraída no pertenece al vocabulario real del cliente,
    # no la enviamos a CLIP. Cuando además hay color explícito, priorizamos ese
    # color por encima de modificadores ruidosos.
    if not category_matches_client_vocab and explicit_color:
        phrase_tokens = [explicit_color]
    else:
        phrase_tokens = ([category] if category else []) + normalized_modifiers

    phrase_tokens = [t for t in phrase_tokens if t]
    phrase_tokens = list(dict.fromkeys(phrase_tokens))
    return " ".join(phrase_tokens).strip()


def stage2_precise_rerank(query_text: str, candidates: list, limit: int = 10):
    # STAGE 2 NUEVO: CLIP query(text) vs embeddings de imágenes de productos.
    if not candidates:
        return []

    start_time = time.time()
    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    with torch.no_grad():
        text_inputs = clip_processor(
            text=[query_text],
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(device)
        query_embedding = clip_model.get_text_features(**text_inputs)
        query_embedding = query_embedding / query_embedding.norm(dim=-1, keepdim=True)
        query_vec = query_embedding.squeeze(0).cpu().numpy().astype(np.float32)

    scored_candidates = []

    for product in candidates:
        best_similarity = -1.0
        best_image = None

        for img in (product.images or []):
            if not img.clip_embedding:
                continue
            try:
                import json
                img_vec = np.array(json.loads(img.clip_embedding), dtype=np.float32)
                img_norm = np.linalg.norm(img_vec)
                if img_norm == 0:
                    continue
                img_vec = img_vec / img_norm
                similarity = float(np.dot(query_vec, img_vec))
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_image = img
            except Exception:
                continue

        if best_image is None:
            continue

        scored_candidates.append({
            'product': product,
            'similarity': best_similarity,
            'image': best_image
        })

    scored_candidates.sort(key=lambda x: x['similarity'], reverse=True)
    top_results = scored_candidates[:limit]

    elapsed = time.time() - start_time
    log_search(f"STAGE 2 (NUEVO CLIP img): Top {len(top_results)} rerankeados en {elapsed:.3f}s")
    for i, result in enumerate(top_results[:3], 1):
        log_verbose(LogCategory.SEARCH, f"   {i}. {result['product'].name} (sim: {result['similarity']:.3f})")

    return top_results


@bp.route("/search/text/legacy", methods=["POST", "OPTIONS"])
def text_search_legacy():
    # Endpoint de búsqueda textual V2 (Broad Recall + CLIP Reranking).
    # Documentación extendida movida a README o docs para evitar errores de comillas.
    # Manejar preflight OPTIONS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

    start_time = time.time()

    def _hang_trace(msg: str):
        return None

    # Rollback defensivo inicial para limpiar cualquier transacción abortada previa
    try:
        db.session.rollback()
    except Exception:
        pass

    try:
        # Validar API Key
        client, error = verify_api_key()
        if error:
            return jsonify({
                "success": False,
                "error": "unauthorized",
                "message": error
            }), 401

        # Obtener parámetros
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "bad_request",
                "message": "Query requerido"
            }), 400

        query_text = data.get('query', '').strip()
        if not query_text:
            return jsonify({
                "success": False,
                "error": "bad_request",
                "message": "Query vacío"
            }), 400

        # Obtener límite del sistema (igual que en api.py)
        default_max_results = system_config.get('search', 'max_results', 10)
        limit = min(int(data.get('limit', default_max_results)), default_max_results)
        # Límite por categoría configurable por request/cliente (fallback: limit)
        per_category_limit = min(
            int(data.get('max_results_per_category', limit)),
            default_max_results
        )
        if per_category_limit < 1:
            per_category_limit = 1

        # Configuración por cliente (alineada con búsqueda visual)
        try:
            client_api_settings = _json_nlp.loads(client.api_settings) if getattr(client, 'api_settings', None) else {}
            if not isinstance(client_api_settings, dict):
                client_api_settings = {}
        except Exception:
            client_api_settings = {}
        color_priority_enabled = bool(client_api_settings.get('color_priority_enabled', False))

        log_search(f"[TEXT_SEARCH] Query original recibida: '{query_text}'")

        # 🆕 Cargar perfil de búsqueda del cliente
        try:
            client_profile = SearchProfilesService.get_profile(str(client.id), client.industry)
            log_verbose(LogCategory.NLP, f"[PROFILE] Perfil cargado: {client_profile.get('name', 'unknown')} (industry: {client.industry})")
        except Exception as e:
            log_error(f"Error cargando perfil de búsqueda: {e}")
            client_profile = None

        # Paso 0: Normalización semántica de la frase (spaCy)
        log_verbose(LogCategory.SEARCH, f"[TEXT_SEARCH] Llamando a extractor...")
        extraction_result = _extract_key_terms_with_dependency_parsing(query_text, client_profile)
        log_verbose(LogCategory.SEARCH, f"[TEXT_SEARCH] Extractor devolvió: {extraction_result}")
        _hang_trace("POST extractor: resultado recibido")

        cleaned_query = extraction_result.get('text', '')
        if cleaned_query and cleaned_query.strip() and extraction_result.get('success'):
            classification_done = False  # Flag para evitar doble clasificación contradictoria
            _hang_trace("PRE-STAGE1 bloque diagnóstico: inicio")
            run_legacy_pre_stage_pipeline = bool(data.get('run_legacy_pre_stage_pipeline', False))
            configured_attributes = []
            matched_categories = []
            matched_category_ids = []
            modificadores = extraction_result.get('modifiers', []) or []
            atributos_encontrados = []
            modificadores_no_configurados = []
            log_verbose(LogCategory.NLP, f"[TEXT_SEARCH] Preprocesamiento exitoso: '{query_text}' → '{cleaned_query}'")
            log_verbose(LogCategory.NLP, f"   📦 Categoría extraída: '{extraction_result.get('category')}'")
            log_verbose(LogCategory.NLP, f"   🏷️  Modificadores extraídos: {extraction_result.get('modifiers')}")

            # 🛑 PUNTO DE CORTE PARA TESTING
            # Obtener categorías del cliente
            try:
                if not run_legacy_pre_stage_pipeline:
                    _hang_trace("PRE-STAGE1 legacy pipeline omitido (default)")
                    raise RuntimeError("__SKIP_LEGACY_PRE_STAGE__")

                _hang_trace("PRE-STAGE1: consultando categorías activas del cliente")
                client_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
                _hang_trace(f"PRE-STAGE1: categorías activas cargadas={len(client_categories)}")
                log_verbose(LogCategory.SEARCH, "="*60)
                log_verbose(LogCategory.CATEGORY_DETECTION, f"🔍 DETECCIÓN DE CATEGORÍAS DEL CLIENTE")
                log_verbose(LogCategory.NLP, "="*60)
                log_verbose(LogCategory.CATEGORY_DETECTION, f"Total categorías activas del cliente: {len(client_categories)}")

                # Buscar coincidencias con la categoría extraída
                categoria_extraida = extraction_result.get('category')
                matched_categories = []
                matched_category_ids = []

                # 🆕 Expandir categoría con sinónimos del perfil
                category_variants = {categoria_extraida}  # Incluir la original
                if client_profile and isinstance(client_profile.get('category_synonyms'), dict):
                    profile_synonyms = client_profile.get('category_synonyms', {})
                    # Si la categoría está en el mapa de sinónimos, agregar sus variantes
                    if categoria_extraida in profile_synonyms:
                        variants = profile_synonyms[categoria_extraida]
                        if isinstance(variants, (list, set, tuple)):
                            category_variants.update(variants)
                    # También buscar si la categoría es sinónimo de alguna otra
                    for base_cat, syns in profile_synonyms.items():
                        if isinstance(syns, (list, set, tuple)) and categoria_extraida in syns:
                            category_variants.add(base_cat)

                if len(category_variants) > 1:
                    log_verbose(LogCategory.NLP, f"[PROFILE SYNONYMS] Expandidas variantes de '{categoria_extraida}': {category_variants}")

                for cat in client_categories:
                    # Tokenizar nombre de categoría (igual que hace el módulo custom)
                    cat_tokens = set()
                    if cat.name:
                        # Tokenizar: "Delantal Completo" → ["delantal", "completo"]
                        cat_tokens.update(_normalize_tokens_es(cat.name))
                    if cat.name_en:
                        cat_tokens.update(_normalize_tokens_es(cat.name_en))
                    if cat.alternative_terms:
                        for term in cat.alternative_terms.split(','):
                            term = term.strip()
                            if term:
                                cat_tokens.update(_normalize_tokens_es(term))

                    # Verificar si la categoría extraída O sus sinónimos están en tokens de la categoría
                    matched_variant = None
                    for variant in category_variants:
                        if variant and variant.lower() in cat_tokens:
                            matched_variant = variant
                            break

                    if matched_variant:
                        matched_categories.append({
                            'id': cat.id,
                            'name': cat.name,
                            'name_en': cat.name_en,
                            'slug': cat.slug
                        })
                        matched_category_ids.append(cat.id)
                        log_verbose(LogCategory.CATEGORY_DETECTION, f"✅ Match encontrado: '{cat.name}' (id: {cat.id}) via '{matched_variant}' - tokens: {cat_tokens}")

                    _hang_trace(f"PRE-STAGE1: category matching listo, matched_categories={len(matched_categories)}")

                print(f"\n📊 RESUMEN DE DETECCIÓN:")
                log_verbose(LogCategory.CATEGORY_DETECTION, f"   Categoría en query: '{categoria_extraida}'")
                log_verbose(LogCategory.CATEGORY_DETECTION, f"   Categorías coincidentes: {len(matched_categories)}")
                if matched_categories:
                    for mc in matched_categories:
                        log_verbose(LogCategory.NLP, f"      - {mc['name']} ({mc['slug']})")
                else:
                    log_verbose(LogCategory.NLP, f"      ⚠️ No se encontraron coincidencias")

                # PASO 2: ANÁLISIS DE MODIFICADORES vs ATRIBUTOS CONFIGURADOS
                log_verbose(LogCategory.SEARCH, "="*60)
                log_verbose(LogCategory.NLP, f"🏷️  ANÁLISIS DE MODIFICADORES")
                log_verbose(LogCategory.NLP, "="*60)

                modificadores = extraction_result.get('modifiers', [])
                print(f"Modificadores detectados: {modificadores if modificadores else '(ninguno)'}")

                # === COLOR TOKENS DEL PERFIL (DETECCIÓN DIRECTA EN LA QUERY) ===
                try:
                    profile_colors = set()
                    if client_profile and isinstance(client_profile.get('color_tokens'), (list, set, tuple)):
                        profile_colors = {str(c).strip().lower() for c in client_profile.get('color_tokens', []) if c}
                    if profile_colors:
                        nlp_colors_direct = _get_nlp_es()
                        if nlp_colors_direct is not None:
                            doc_colors_direct = nlp_colors_direct(query_text)
                            added = []
                            for tok in doc_colors_direct:
                                tl = tok.text.lower()
                                if tl in profile_colors and tl not in modificadores:
                                    modificadores.append(tl)
                                    added.append(tl)
                            if added:
                                print(f"🎨 [PROFILE COLOR] Añadidos por perfil: {added}")
                        else:
                            # Fallback simple sin spaCy: split básico
                            for tl in (t.strip().lower() for t in query_text.split()):
                                if tl in profile_colors and tl not in modificadores:
                                    modificadores.append(tl)
                            print("🎨 [PROFILE COLOR] Añadidos (fallback split) colores del perfil si estaban en query")
                except Exception as e_prof_col:
                    print(f"[PROFILE COLOR] ⚠️ Error integrando color_tokens del perfil: {e_prof_col}")

                # === MAPE0 SEMÁNTICO DE COLORES SISTÉMICOS (ANTES DE CLASIFICAR ATRIBUTOS) ===
                try:
                    _hang_trace("PRE-STAGE1: inicio mapeo semántico de colores")
                    from app.utils.semantic_colors import map_semantic_colors, get_system_color_adjectives
                    system_color_adjectives = set(get_system_color_adjectives())
                    # Detectar adjetivos sistémicos presentes en la query original (aunque no hayan quedado como modificadores)
                    nlp_colors = _get_nlp_es()
                    sys_color_tokens = []
                    if nlp_colors is not None:
                        doc_colors = nlp_colors(query_text)
                        for tok in doc_colors:
                            tl = tok.text.lower()
                            if tl in system_color_adjectives:
                                sys_color_tokens.append(tl)
                    if sys_color_tokens:
                        print(f"\n🎨 [SEMANTIC COLOR] Adjetivos sistémicos detectados en query: {sys_color_tokens}")
                        # Obtener lista de valores de color del cliente para similitud
                        from app.models.product_attribute_config import ProductAttributeConfig as _PAC_SM
                        cfgs_color = _PAC_SM.query.filter_by(client_id=client.id).all()
                        color_cfg = next(
                            (
                                cfg for cfg in cfgs_color
                                if (cfg.key or '').strip().lower() == 'color'
                                or 'color' in (cfg.key or '').strip().lower()
                            ),
                            None
                        )
                        client_color_values = []
                        if color_cfg and color_cfg.options:
                            raw_opt = color_cfg.options
                            try:
                                import json as _json_sm, unicodedata as _ud_sm
                                if isinstance(raw_opt, list):
                                    client_color_values = raw_opt
                                elif isinstance(raw_opt, dict):
                                    if 'values' in raw_opt and isinstance(raw_opt['values'], list):
                                        client_color_values = raw_opt['values']
                                    else:
                                        client_color_values = list(raw_opt.keys())
                                elif isinstance(raw_opt, str):
                                    parsed = _json_sm.loads(raw_opt)
                                    if isinstance(parsed, list):
                                        client_color_values = parsed
                                    elif isinstance(parsed, dict):
                                        if 'values' in parsed and isinstance(parsed['values'], list):
                                            client_color_values = parsed['values']
                                        else:
                                            client_color_values = list(parsed.keys())
                            except Exception as e_color_parse:
                                print(f"[SEMANTIC COLOR] ⚠️ Error parseando opciones de color: {e_color_parse}")
                        if client_color_values:
                            color_map = map_semantic_colors(sys_color_tokens, client_color_values)
                            for adj_norm, pairs in color_map.items():
                                if not pairs:
                                    print(f"[SEMANTIC COLOR] Sin similitudes suficientes para '{adj_norm}'")
                                    continue
                                print(f"[SEMANTIC COLOR] '{adj_norm}' → candidatos: {[(c, round(s,3)) for c,s in pairs]} TODO añadir a modificadores")
                                for color_val, score in pairs:
                                    # Evitar duplicados y no añadir si ya existe literal en modificadores
                                    col_norm = color_val.strip().lower()
                                    if col_norm not in modificadores:
                                        modificadores.append(col_norm)
                                        print(f"   ➕ Añadido color semántico '{color_val}' (score {score:.3f}) a modificadores")
                        else:
                            print("[SEMANTIC COLOR] ⚠️ Cliente sin valores de color configurados, se omite similitud")
                    else:
                        print("[SEMANTIC COLOR] No hay adjetivos sistémicos en la query")
                    _hang_trace("PRE-STAGE1: fin mapeo semántico de colores")
                except Exception as e_sem_col:
                    print(f"[SEMANTIC COLOR] ⚠️ Error en mapeo semántico de colores: {e_sem_col}")
                    _hang_trace("PRE-STAGE1: excepción en mapeo semántico de colores")

                # Cargar atributos configurados para este cliente
                from app.models.product_attribute_config import ProductAttributeConfig
                _hang_trace("PRE-STAGE1: consultando atributos configurados")
                configured_attributes = ProductAttributeConfig.query.filter_by(
                    client_id=client.id
                ).order_by(ProductAttributeConfig.field_order).all()
                _hang_trace(f"PRE-STAGE1: atributos configurados cargados={len(configured_attributes)}")

                # Crear mapa de atributos: key -> label (para identificación)
                attribute_keys = {}  # key normalizado -> objeto config
                attribute_labels = {}  # label normalizado -> objeto config

                print(f"\nAtributos configurados en el sistema ({len(configured_attributes)}):")
                for attr in configured_attributes:
                    key_norm = (attr.key or '').strip().lower()
                    label_norm = (attr.label or '').strip().lower()
                    if key_norm:
                        attribute_keys[key_norm] = attr
                    if label_norm:
                        attribute_labels[label_norm] = attr
                    print(f"   - {attr.label} (key: '{attr.key}', type: {attr.type})")

                # Analizar cada modificador
                atributos_encontrados = []  # Modificadores que SÍ son atributos configurados
                modificadores_no_configurados = []  # Modificadores que NO son atributos

                print(f"\n🔍 Comparando modificadores contra atributos configurados:")
                _hang_trace(f"PRE-STAGE1: inicio clasificación de modificadores total={len(modificadores)}")
                for mod in modificadores:
                    mod_norm = mod.strip().lower()
                    _hang_trace(f"PRE-STAGE1: clasificando modificador='{mod_norm}'")

                    # Buscar coincidencia flexible (key o label, con variaciones)
                    matched = False
                    matched_config = None
                    match_type = None

                    # 1. Coincidencia exacta con key
                    if mod_norm in attribute_keys:
                        matched = True
                        matched_config = attribute_keys[mod_norm]
                        match_type = 'key'

                    # 2. Coincidencia exacta con label
                    elif mod_norm in attribute_labels:
                        matched = True
                        matched_config = attribute_labels[mod_norm]
                        match_type = 'label'

                    # 3. Coincidencia parcial (singular/plural, sufijos)
                    else:
                        # Buscar si el modificador está CONTENIDO en algún key/label
                        for key_n, cfg in attribute_keys.items():
                            if mod_norm in key_n or key_n in mod_norm:
                                matched = True
                                matched_config = cfg
                                match_type = 'key_partial'
                                break

                        if not matched:
                            for label_n, cfg in attribute_labels.items():
                                if mod_norm in label_n or label_n in mod_norm:
                                    matched = True
                                    matched_config = cfg
                                    match_type = 'label_partial'
                                    break

                    # 4. Coincidencia con valores de atributos tipo 'list' (ej: "negro" → color)
                    # FIX: Antes tomábamos las keys del dict ("values", "multiple") en vez de la lista real de valores.
                    if not matched:
                        for cfg in configured_attributes:
                            if cfg.type == 'list' and cfg.options:
                                try:
                                    import json, unicodedata as _ud

                                    raw_opt = cfg.options
                                    options = []

                                    # Caso 1: lista directa
                                    if isinstance(raw_opt, list):
                                        options = raw_opt
                                    # Caso 2: dict → buscar clave 'values'
                                    elif isinstance(raw_opt, dict):
                                        if 'values' in raw_opt and isinstance(raw_opt['values'], list):
                                            options = raw_opt['values']
                                        else:
                                            # fallback: usar keys como antes (pero poco común)
                                            options = list(raw_opt.keys())
                                    # Caso 3: string (JSON) → parsear y aplicar misma lógica
                                    elif isinstance(raw_opt, str):
                                        parsed = json.loads(raw_opt)
                                        if isinstance(parsed, list):
                                            options = parsed
                                        elif isinstance(parsed, dict):
                                            if 'values' in parsed and isinstance(parsed['values'], list):
                                                options = parsed['values']
                                            else:
                                                options = list(parsed.keys())
                                        else:
                                            continue
                                    else:
                                        continue

                                    # Normalización acento-insensible + lower
                                    def _norm_val(v):
                                        txt = str(v).strip().lower()
                                        txt = ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')
                                        return txt

                                    options_norm = [_norm_val(opt) for opt in options if str(opt).strip()]

                                    # DEBUG restringido a colores y modificadores frecuentes
                                    if (cfg.key or '').strip().lower() == 'color' or mod_norm in (
                                        'negro','rojo','azul','verde','gris','blanco','amarillo','marron','beige','rosa','violeta','morado'
                                    ):
                                        log_verbose(LogCategory.NLP, f"      [VAL-MATCH DEBUG] Evaluando modificador '{mod_norm}' contra valores de '{cfg.key}': raw={raw_opt}")
                                        log_verbose(LogCategory.NLP, f"      [VAL-MATCH DEBUG] Valores normalizados de '{cfg.key}': {options_norm}")

                                    if mod_norm in options_norm:
                                        matched = True
                                        matched_config = cfg
                                        match_type = 'value'
                                        matched_value = options[options_norm.index(mod_norm)]
                                        log_verbose(LogCategory.NLP, f"      [VAL-MATCH DEBUG] MATCH por valor: '{mod_norm}' ∈ {options_norm} (atributo '{cfg.key}') → valor original: {matched_value}")
                                        break
                                    else:
                                        if (cfg.key or '').strip().lower() == 'color' or mod_norm in (
                                            'negro','rojo','azul','verde','gris','blanco','amarillo','marron','beige','rosa','violeta','morado'
                                        ):
                                            log_verbose(LogCategory.NLP, f"      [VAL-MATCH DEBUG] SIN MATCH valor: '{mod_norm}' no está en valores de '{cfg.key}'")
                                except Exception as e:
                                    log_verbose(LogCategory.NLP, f"         ⚠️ Error parseando opciones de '{cfg.label}': {e}")
                                    continue

                    if matched and matched_config:
                        match_info = {
                            'modificador_original': mod,
                            'atributo_key': matched_config.key,
                            'atributo_label': matched_config.label,
                            'atributo_type': matched_config.type,
                            'match_tipo': match_type
                        }
                        # Si matcheó por valor, incluir el valor detectado
                        if match_type == 'value':
                            match_info['valor_detectado'] = matched_value

                        atributos_encontrados.append(match_info)

                        if match_type == 'value':
                            print(f"   ✅ '{mod}' → Match con valor de '{matched_config.label}' (key: {matched_config.key}, valor: {matched_value})")
                        else:
                            print(f"   ✅ '{mod}' → Match con atributo '{matched_config.label}' (key: {matched_config.key}, tipo: {match_type})")
                    else:
                        modificadores_no_configurados.append(mod)
                        print(f"   ❌ '{mod}' → NO es un atributo configurado")

                _hang_trace(
                    f"PRE-STAGE1: clasificación de modificadores lista matched={len(atributos_encontrados)} "
                    f"unmatched={len(modificadores_no_configurados)}"
                )

                print(f"\n📊 RESULTADO CLASIFICACIÓN:")
                print(f"   ✅ Atributos encontrados: {len(atributos_encontrados)}")
                print(f"   ❌ Modificadores NO configurados: {len(modificadores_no_configurados)}")
                classification_done = True

                # PASO 3: FILTRADO HÍBRIDO CON CLIP
                log_verbose(LogCategory.SEARCH, "="*60)
                print(f"🔍 FILTRADO HÍBRIDO: SQL + CLIP")
                log_verbose(LogCategory.NLP, "="*60)

                # 3.1: Obtener productos de las categorías detectadas
                if not matched_category_ids:
                    print(f"⚠️ Sin categorías detectadas, no se puede filtrar")
                    # Recuperar TODAS las categorías activas del cliente para que el frontend pueda mostrar chips
                    try:
                        all_active_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
                        available_names = [c.name for c in all_active_categories]
                    except Exception as _cat_err:
                        print(f"⚠️ Error obteniendo categorías activas: {_cat_err}")
                        available_names = []
                    # Antes de retornar error, registrar analytics para no perder el conteo
                    try:
                        import time as _t
                        print(f"🔍 ANALYTICS (no_category): Registrando búsqueda sin categoría para client={client.id}", flush=True)

                        # Fase 1: términos claros
                        terms_extracted = [str(m).lower() for m in (modificadores or []) if str(m).strip()]
                        terms_matched = [
                            str(af.get('modificador_original')).lower()
                            for af in (atributos_encontrados or [])
                            if af.get('modificador_original')
                        ]
                        terms_unmatched = [str(m).lower() for m in (modificadores_no_configurados or []) if str(m).strip()]

                        # Intentar marcar la categoría solicitada (sustantivo principal) como missing si existe
                        categoria_solicitada = None
                        try:
                            # categoria_extraida definida arriba por extractor
                            if 'categoria_extraida' in locals() and categoria_extraida:
                                categoria_solicitada = categoria_extraida.strip()
                        except Exception:
                            categoria_solicitada = None
                        categories_detected_log = None
                        categories_missing_log = None
                        if categoria_solicitada:
                            # Evitar marcar si coincide exactamente con alguna disponible
                            if categoria_solicitada not in available_names:
                                categories_detected_log = [categoria_solicitada]
                                categories_missing_log = [categoria_solicitada]

                        elapsed_ms = int((_t.time() - start_time) * 1000)
                        SearchLog.log_search(
                            client_id=client.id,
                            search_type='text',
                            query_text=query_text,
                            image_url=None,
                            categories_detected=categories_detected_log,
                            categories_matched=None,
                            categories_missing=categories_missing_log,
                            terms_extracted=terms_extracted or None,
                            terms_matched=terms_matched or None,
                            terms_unmatched=terms_unmatched or None,
                            results_count=0,
                            had_results=False,
                            response_time_ms=elapsed_ms
                        )
                        print(f"✅ ANALYTICS (no_category): SearchLog.log_search() completado", flush=True)
                    except Exception as _log_nc:
                        import traceback as _tb
                        print(f"❌ ANALYTICS (no_category) ERROR: {_log_nc}", flush=True)
                        print(f"   Traceback: {_tb.format_exc()}", flush=True)

                    # Respuesta enriquecida (mantiene error para UI roja, pero incluye datos de categorías)
                    return jsonify({
                        "success": False,
                        "error": "no_category",
                        "message": "No se detectó ninguna categoría válida",
                        "categories_available": available_names,
                        "categories_searched": available_names,
                        "category_requested": categoria_solicitada
                    })

                base_products = Product.query.filter(
                    Product.client_id == client.id,
                    Product.category_id.in_(matched_category_ids),
                    Product.is_active == True
                ).all()

                print(f"\n📦 Base de productos (categorías detectadas): {len(base_products)} productos")

                # Inicializar set de fallback products (usado más adelante si es necesario)
                fallback_product_ids = set()

                # 3.2: Aplicar FILTRADO FUERTE (atributos configurados)
                filtered_products = base_products
                if atributos_encontrados:
                    print(f"\n🔒 Aplicando filtrado FUERTE (SQL) para atributos configurados:")
                    # Construir mapa de filtros por valor cuando corresponda
                    # key -> set(valores_normalizados_aceptados)
                    attr_value_filters = {}
                    def _norm_val_filter(v):
                        import unicodedata as _ud
                        txt = str(v).strip().lower()
                        txt = ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')
                        if txt in ('si','sí'):  # unificar sí/si
                            txt = 'si'
                        return txt

                    for attr_match in atributos_encontrados:
                        attr_key = attr_match['atributo_key']
                        match_tipo = attr_match.get('match_tipo')
                        valor_detectado = attr_match.get('valor_detectado')
                        # Caso match por valor explícito
                        if match_tipo == 'value' and valor_detectado is not None:
                            attr_value_filters.setdefault(attr_key, set()).add(_norm_val_filter(valor_detectado))
                        # Caso especial: atributo bolsillo (con_bolsillo) detectado sólo por label/key → asumir presencia "Si"
                        elif match_tipo in ('label','key') and attr_key == 'con_bolsillo':
                            attr_value_filters.setdefault(attr_key, set()).add('si')
                        else:
                            # Sin valor específico → sólo presencia (no filtra por valor)
                            pass
                        print(f"   ℹ️  Atributo '{attr_key}' detectado (tipo match: {match_tipo})")

                    # Aplicar scoring progresivo por atributos (no exclusión estricta)
                    if attr_value_filters:
                        before_count = len(filtered_products)
                        scored_by_attrs = []
                        total_criteria = len(attr_value_filters)

                        # 🎯 3 NIVELES DE SCORING:
                        # 1. SQL match (tiene atributo Y coincide)
                        # 2. Sin atributo (pasa a CLIP para inferencia)
                        # 3. Tiene atributo pero NO coincide (fallback)

                        sql_matches = []      # Tier 1: Coincidencia SQL exacta
                        for_clip_inference = []  # Tier 2: Sin atributo → CLIP decide
                        no_matches = []       # Tier 3: Tiene atributo diferente

                        for prod in filtered_products:
                            attrs = prod.attributes or {}
                            matches = 0
                            match_details = {}
                            has_any_requested_attr = False  # Tiene alguno de los atributos solicitados en BD

                            # Contar cuántos atributos coinciden
                            for k, accepted in attr_value_filters.items():
                                raw_val = attrs.get(k)
                                if raw_val is not None:
                                    has_any_requested_attr = True
                                    norm_val = _norm_val_filter(raw_val)
                                    if norm_val in accepted:
                                        matches += 1
                                        match_details[k] = norm_val

                            item = {
                                'product': prod,
                                'attr_matches': matches,
                                'attr_total': total_criteria,
                                'attr_score': matches / total_criteria if total_criteria > 0 else 0,
                                'match_details': match_details
                            }

                            if matches > 0:
                                # Tier 1: Coincidencia SQL
                                sql_matches.append(item)
                            elif not has_any_requested_attr:
                                # Tier 2: No tiene el atributo en BD → CLIP inferirá
                                for_clip_inference.append(item)
                            else:
                                # Tier 3: Tiene atributo pero no coincide
                                no_matches.append(item)

                        # Ordenar cada tier
                        sql_matches.sort(key=lambda x: x['attr_matches'], reverse=True)

                        print(f"   ✅ Filtrado por atributos aplicado: {attr_value_filters}")
                        print(f"   📊 Distribución:")
                        print(f"      🎯 Tier 1 (SQL match): {len(sql_matches)} productos")
                        print(f"      🔍 Tier 2 (sin atributo, evaluar con CLIP): {len(for_clip_inference)} productos")
                        print(f"      ⚪ Tier 3 (otro valor): {len(no_matches)} productos")

                        # Inicializar producto_attr_scores y filtered_products
                        product_attr_scores = {}
                        filtered_products = []

                        # Agregar Tier 1 (SQL matches)
                        for item in sql_matches:
                            product_attr_scores[item['product'].id] = {**item, 'tier': 1}
                            filtered_products.append(item['product'])

                        # Agregar Tier 2 (para CLIP) - marcar para que CLIP los evalúe después
                        clip_candidates_ids = set()
                        for item in for_clip_inference:
                            product_attr_scores[item['product'].id] = {**item, 'tier': 2, 'needs_clip': True}
                            filtered_products.append(item['product'])
                            clip_candidates_ids.add(item['product'].id)

                        # Tier 3 se mantendrá como fallback potencial
                        fallback_products = no_matches

                        # Tier 3 se mantendrá como fallback potencial
                        fallback_products = no_matches

                        # 🔄 FALLBACK: Si resultados < mínimo de categoría, agregar productos Tier 3
                        MIN_CATEGORY_RESULTS = per_category_limit
                        fallback_product_ids = set()  # IDs de productos agregados como fallback

                        if len(filtered_products) < MIN_CATEGORY_RESULTS and fallback_products:
                            needed = MIN_CATEGORY_RESULTS - len(filtered_products)
                            print(f"   🔄 Fallback: Solo {len(filtered_products)} productos, agregando hasta {needed} de Tier 3")

                            # Tomar los primeros N del fallback
                            fallback_to_add = fallback_products[:needed]

                            for item in fallback_to_add:
                                fallback_product_ids.add(item['product'].id)
                                product_attr_scores[item['product'].id] = {
                                    **item,
                                    'tier': 3,
                                    'is_fallback': True
                                }
                                filtered_products.append(item['product'])

                            print(f"      ✅ Agregados {len(fallback_to_add)} productos fallback")
                    else:
                        print("   ℹ️  Sin restricciones de valor específicas (solo presencia de atributos)")
                        product_attr_scores = {}
                        fallback_product_ids = set()  # Inicializar vacío si no hay filtrado

                print(f"   📦 Productos después de filtrado fuerte: {len(filtered_products)}")

                # Determinar si necesitamos CLIP:
                # 1. Hay modificadores no configurados → siempre usar CLIP
                # 2. Hay productos Tier 2 (sin atributo) → usar CLIP para inferir atributos configurados
                needs_clip = False
                modifiers_for_clip = []

                if modificadores_no_configurados:
                    needs_clip = True
                    modifiers_for_clip = list(modificadores_no_configurados)

                # Verificar si hay productos Tier 2 (sin atributo que necesita CLIP)
                try:
                    tier2_products = [p for p in filtered_products if product_attr_scores.get(p.id, {}).get('tier') == 2]
                    if tier2_products and atributos_encontrados:
                        needs_clip = True
                        # Agregar modificadores de atributos encontrados que no estén ya
                        for attr in atributos_encontrados:
                            mod_detected = attr.get('modificador_original')  # El modificador original (ej: "negro")
                            if mod_detected and mod_detected not in modifiers_for_clip:
                                modifiers_for_clip.append(mod_detected)
                                print(f"      🔍 Agregando '{mod_detected}' para inferencia CLIP en Tier 2")
                except Exception as e:
                    log_error(f"Error construyendo modifiers_for_clip: {e}")

                # Si NO hay filtrado CLIP pero SÍ hay scoring por atributos, ya están ordenados
                # (de mayor a menor coincidencia) desde el paso anterior

                # 3.3: Aplicar INFERENCIA CLIP para modificadores no configurados O productos Tier 2
                if needs_clip and filtered_products:
                    if modificadores_no_configurados:
                        print(f"\n🎯 Aplicando inferencia de ATRIBUTOS (CLIP) para modificadores no configurados:")
                    else:
                        print(f"\n🎯 Aplicando inferencia de ATRIBUTOS (CLIP) para productos sin atributo en BD:")
                    print(f"   Modificadores a evaluar: {modifiers_for_clip}")

                    # Obtener categoría extraída para contexto
                    categoria_extraida = extraction_result.get('category', '')

                    # Almacenar scores de CLIP por modificador y producto
                    clip_inference_scores = {}  # product_id -> {mod -> inference_result}
                    import json

                    try:
                        for product in filtered_products:
                            clip_inference_scores[product.id] = {}

                            # Obtener imagen primaria
                            primary_image = None
                            if product.images:
                                for img in product.images:
                                    if img.is_primary:
                                        primary_image = img
                                        break
                                if not primary_image:
                                    primary_image = product.images[0]

                            if not primary_image or not primary_image.clip_embedding:
                                # Sin imagen/embedding, no puede inferir
                                for mod in modifiers_for_clip:
                                    clip_inference_scores[product.id][mod] = {
                                        'has_attribute': False,
                                        'max_similarity': 0.0,
                                        'confidence': 'no_embedding'
                                    }
                                continue

                            # Parsear embedding de imagen
                            try:
                                image_embedding = json.loads(primary_image.clip_embedding)
                                image_vec = np.array(image_embedding, dtype=np.float32)

                                # 🔧 CRÍTICO: Normalizar el vector de imagen (debe tener norma 1)
                                norm = np.linalg.norm(image_vec)
                                if norm > 0:
                                    image_vec = image_vec / norm

                                # Para cada modificador, inferir si está presente usando embeddings de BD
                                for mod in modifiers_for_clip:
                                    # Intentar obtener embedding precomputado de la tabla embeddings
                                    try:
                                        from app.models.embedding import Embedding
                                        # Buscar embedding en BD (vocab:X, color:X, o key directa)
                                        emb_record = (
                                            Embedding.query.filter_by(key=f"vocab:{mod}", type='vocabulary').first() or
                                            Embedding.query.filter_by(key=f"color:{mod}", type='color').first() or
                                            Embedding.query.filter(Embedding.key.ilike(f"%{mod}%")).first()
                                        )

                                        if emb_record:
                                            # Usar embedding precalculado
                                            mod_vec = np.array(json.loads(emb_record.embedding), dtype=np.float32)

                                            # ⚠️ CRÍTICO: Verificar dimensiones antes de comparar
                                            if mod_vec.shape[0] != image_vec.shape[0]:
                                                print(f"      ⚠️ Dimensiones incompatibles para '{mod}': imagen={image_vec.shape[0]}, texto={mod_vec.shape[0]} - usando fallback")
                                                # Fallback a CLIP con prompts
                                                inference = _infer_attribute_from_clip_cached(
                                                    image_vec,
                                                    mod,
                                                    categoria=categoria_extraida,
                                                    threshold=0.28
                                                )
                                                clip_inference_scores[product.id][mod] = inference
                                                continue

                                            # Normalizar
                                            norm_m = np.linalg.norm(mod_vec)
                                            if norm_m > 0:
                                                mod_vec = mod_vec / norm_m

                                            # Similitud directa
                                            similarity = float(np.dot(image_vec, mod_vec))

                                            # Clasificar confianza
                                            if similarity >= 0.65:
                                                confidence = 'high'
                                                has_attr = True
                                            elif similarity >= 0.28:
                                                confidence = 'medium'
                                                has_attr = True
                                            else:
                                                confidence = 'low'
                                                has_attr = False

                                            clip_inference_scores[product.id][mod] = {
                                                'has_attribute': has_attr,
                                                'max_similarity': similarity,
                                                'confidence': confidence
                                            }
                                        else:
                                            # Fallback: usar función con prompts si no hay embedding en BD
                                            inference = _infer_attribute_from_clip_cached(
                                                image_vec,
                                                mod,
                                                categoria=categoria_extraida,
                                                threshold=0.28
                                            )
                                            clip_inference_scores[product.id][mod] = inference
                                    except Exception as e_emb:
                                        print(f"      ⚠️ Error obteniendo embedding de '{mod}': {e_emb}")
                                        # Fallback
                                        inference = _infer_attribute_from_clip_cached(
                                            image_vec,
                                            mod,
                                            categoria=categoria_extraida,
                                            threshold=0.28
                                        )
                                        clip_inference_scores[product.id][mod] = inference

                            except Exception as e:
                                print(f"      ⚠️ Error parseando embedding de producto {product.id}: {e}")
                                for mod in modifiers_for_clip:
                                    clip_inference_scores[product.id][mod] = {
                                        'has_attribute': False,
                                        'max_similarity': 0.0,
                                        'confidence': 'error'
                                    }

                        # Calcular score CLIP por producto: qué % de modificadores detecta
                        clip_product_scores = {}
                        for prod_id, mod_inferences in clip_inference_scores.items():
                            has_attr_count = sum(1 for inf in mod_inferences.values() if inf.get('has_attribute'))
                            total_mods = len(modifiers_for_clip)
                            match_ratio = has_attr_count / total_mods if total_mods > 0 else 0

                            # Score máx similaridad entre todos los modificadores
                            max_sim = max((inf.get('max_similarity', 0) for inf in mod_inferences.values()), default=0.0)

                            clip_product_scores[prod_id] = {
                                'match_ratio': match_ratio,  # % de atributos detectados
                                'max_similarity': max_sim,    # Similitud máxima
                                'mod_details': mod_inferences
                            }

                        print(f"   ✅ Inferencia CLIP completada para {len(filtered_products)} productos")

                        # 🎯 Actualizar tier de productos según resultados CLIP
                        # Productos Tier 2 con CLIP positivo → mantienen Tier 2 (prioridad media)
                        # Productos Tier 2 con CLIP negativo → bajan a Tier 3 (fallback)
                        tier2_confirmed = []
                        tier2_rejected = []

                        for prod_id, clip_score in clip_product_scores.items():
                            if prod_id in product_attr_scores and product_attr_scores[prod_id].get('tier') == 2:
                                product = product_attr_scores[prod_id]['product']
                                match_ratio = clip_score.get('match_ratio', 0)
                                max_sim = clip_score.get('max_similarity', 0)

                                # Cambio: SIN threshold hard, reordenar por score (no rechazar)
                                # Si match_ratio > 0, marcar confirmado; si no, marcar con baja prioridad
                                composite_score = (match_ratio * 100) + (max_sim * 10)

                                if match_ratio > 0:
                                    # Al menos un atributo coincidió
                                    product_attr_scores[prod_id]['clip_confirmed'] = True
                                    product_attr_scores[prod_id]['clip_score'] = clip_score
                                    product_attr_scores[prod_id]['composite_score'] = composite_score
                                    tier2_confirmed.append((product.name, match_ratio, max_sim, composite_score))
                                else:
                                    # Ningún atributo coincidió, pero NO rechazar (mantener en Tier 2 con score bajo)
                                    product_attr_scores[prod_id]['clip_low_score'] = True
                                    product_attr_scores[prod_id]['clip_score'] = clip_score
                                    product_attr_scores[prod_id]['composite_score'] = composite_score
                                    tier2_rejected.append((product.name, max_sim, composite_score))

                        # Mostrar resultados de inferencia CLIP
                        print(f"\n   📊 Resultados inferencia CLIP Tier 2:")
                        if tier2_confirmed:
                            print(f"      ✅ Confirmados ({len(tier2_confirmed)}):")
                            for name, ratio, sim, comp_score in sorted(tier2_confirmed, key=lambda x: x[-1], reverse=True)[:5]:
                                print(f"         • {name}: ratio={ratio:.2f}, sim={sim:.3f}, score={comp_score:.2f}")
                        if tier2_rejected:
                            print(f"      📊 Sin match pero en ranking ({len(tier2_rejected)}):")
                            for name, sim, comp_score in sorted(tier2_rejected, key=lambda x: x[-1], reverse=True)[:5]:
                                print(f"         • {name}: sim={sim:.3f}, score={comp_score:.2f}")

                    except Exception as e_clip:
                        import traceback
                        print(f"\n❌ ERROR en inferencia CLIP: {e_clip}")
                        print(f"   Traceback: {traceback.format_exc()}")
                        log_error(f"Error en inferencia CLIP: {e_clip}\n{traceback.format_exc()}")
                        clip_product_scores = {prod.id: {'match_ratio': 0, 'max_similarity': 0} for prod in filtered_products}
                else:
                    print(f"\n📝 Sin necesidad de inferencia CLIP")
                    clip_product_scores = {}

                # Reordenar productos combinando tier, coincidencias SQL y score CLIP
                try:
                    ranked_products = []
                    for prod in filtered_products:
                        meta = product_attr_scores.get(prod.id, {}) if 'product_attr_scores' in locals() else {}
                        clip = clip_product_scores.get(prod.id, {}) if 'clip_product_scores' in locals() else {}

                        tier = meta.get('tier', 3)
                        attr_score = meta.get('attr_score', 0)
                        composite_score = meta.get('composite_score', 0)  # (match_ratio*100 + max_sim*10)
                        is_fallback = meta.get('is_fallback', False)

                        # Tier 1: priorizar attr_score
                        # Tier 2: priorizar composite_score (match_ratio + max_sim)
                        # Tier 3: se queda al final
                        primary_score = composite_score if tier == 2 else attr_score

                        ranked_products.append((
                            tier,
                            -primary_score,
                            -attr_score,
                            is_fallback,
                            prod
                        ))

                    ranked_products.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
                    filtered_products = [item[-1] for item in ranked_products]
                except Exception as e_sort:
                    log_error(f"Error ordenando productos post-CLIP: {e_sort}")

                # ✅ FORMATEAR RESULTADOS para el widget (formato compatible)
                formatted_results = []
                for product in filtered_products:
                    # Obtener imagen principal
                    primary_image = Image.query.filter_by(
                        product_id=product.id,
                        is_primary=True
                    ).first()

                    if not primary_image:
                        primary_image = Image.query.filter_by(
                            product_id=product.id
                        ).first()

                    # Priorizar external_url (Tiendanube/externo) sobre url_producto (atributo custom)
                    prod_attrs = product.attributes or {}
                    final_product_url = None
                    if hasattr(product, 'external_url') and product.external_url:
                        final_product_url = product.external_url
                    elif prod_attrs.get('url_producto'):
                        raw_url = prod_attrs.get('url_producto')
                        if isinstance(raw_url, dict):
                            final_product_url = raw_url.get('value') or raw_url.get('url') or None
                        else:
                            final_product_url = raw_url

                    # Score de similitud (si existe clip_product_scores)
                    try:
                        clip_score = clip_product_scores.get(product.id, {}) if 'clip_product_scores' in locals() else {}
                        similarity = clip_score.get('max_similarity', 0.0) if clip_score else 0.0
                    except:
                        similarity = 0.0

                    # Cobertura de atributos fuertes (para que el widget calcule % correctamente)
                    try:
                        def _attr_exists(_val):
                            if _val is None:
                                return False
                            if isinstance(_val, bool):
                                return bool(_val)
                            if isinstance(_val, (list, tuple, set, dict)):
                                return len(_val) > 0
                            _s = str(_val).strip().lower()
                            return _s not in ('', 'no', 'false', '0', 'none', 'null')

                        strong_attr_map = []
                        for _a in (atributos_encontrados or []):
                            key = (_a.get('atributo_key') or '').strip()
                            if not key:
                                continue
                            strong_attr_map.append({
                                'key': key,
                                'label': (_a.get('atributo_label') or key).strip()
                            })

                        coverage = []
                        for _m in strong_attr_map:
                            _k = (_m.get('key') or '').strip()
                            _label = (_m.get('label') or _k).strip()
                            _val = (prod_attrs or {}).get(_k)
                            _exists = _attr_exists(_val)
                            coverage.append({
                                'key': _k,
                                'label': _label,
                                'exists': bool(_exists),
                                'value': _val
                            })
                    except Exception:
                        coverage = []

                    formatted_results.append({
                        "id": product.id,
                        "name": product.name,
                        "price": float(product.price) if product.price is not None else None,
                        "similarity": round(similarity, 3),
                        "final_score": round(similarity, 3),
                        "image": primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                        "image_url": primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                        "category": product.category.name if product.category else None,
                        "attributes": prod_attrs,
                        "attributes_coverage": coverage,
                        "weak_modifiers": modificadores_no_configurados or [],
                        "clip_similarity": round(similarity, 3),
                        "similarity_score": round(similarity, 3),
                        "sku": product.sku,
                        "stock": product.stock,
                        "product_url": final_product_url
                    })

                print(f"✅ Formateados {len(formatted_results)} productos para respuesta")

                # ⭐ AGRUPACIÓN POR CATEGORÍAS HERMANAS (si hay múltiples categorías detectadas)
                results_by_category = {}
                group_by_category = False
                MIN_CATEGORY_RESULTS = per_category_limit

                # Construir detection_metadata con matched_categories
                detection_metadata = {
                    'matched_categories': matched_categories  # Lista de dicts con {id, name, slug}
                }

                print(f"\n🎯 AGRUPACIÓN - DIAGNÓSTICO:")
                print(f"   matched_categories: {len(matched_categories)}")
                print(f"   formatted_results: {len(formatted_results)}")

                if detection_metadata and len(detection_metadata.get('matched_categories', [])) > 1:
                    group_by_category = True
                    print(f"   ✅ Activando agrupación (múltiples categorías detectadas)")

                    # Agrupar por categoría
                    for result in formatted_results:
                        cat_name = result.get('category')
                        if cat_name:
                            if cat_name not in results_by_category:
                                results_by_category[cat_name] = []
                            # Limitar a MIN_CATEGORY_RESULTS por categoría
                            if len(results_by_category[cat_name]) < MIN_CATEGORY_RESULTS:
                                results_by_category[cat_name].append(result)

                    print(f"   📊 Distribución inicial:")
                    for cat, items in results_by_category.items():
                        print(f"      • {cat}: {len(items)} productos")

                    # Top-up: completar categorías con < MIN_CATEGORY_RESULTS
                    for cat_name, items in results_by_category.items():
                        if len(items) < MIN_CATEGORY_RESULTS:
                            needed = MIN_CATEGORY_RESULTS - len(items)
                            print(f"   🔄 Top-up para '{cat_name}': necesita {needed} más")

                            # Buscar productos disponibles de esa categoría que no estén ya incluidos
                            existing_ids = {r['id'] for r in items}
                            available = [r for r in formatted_results if r.get('category') == cat_name and r['id'] not in existing_ids]

                            # Agregar hasta completar
                            to_add = available[:needed]
                            results_by_category[cat_name].extend(to_add)
                            print(f"      ✅ Agregados {len(to_add)} productos a '{cat_name}'")

                    print(f"   📊 Distribución final:")
                    for cat, items in results_by_category.items():
                        print(f"      • {cat}: {len(items)} productos")
                else:
                    print(f"   ℹ️  Sin agrupación (categoría única o ninguna)")

                # Construir respuesta compatible con widget
                elapsed = time.time() - start_time

                # Calcular exposed_attribute_keys y exposed_attribute_labels
                exposed_attribute_keys = []
                exposed_attribute_labels = {}
                try:
                    for cfg in configured_attributes:
                        key_l = (cfg.key or '').strip().lower()
                        if not key_l:
                            continue
                        # Lista de atributos visibles
                        if cfg.expose_in_search:
                            exposed_attribute_keys.append(key_l)
                        # Mapa de etiquetas para TODOS los atributos
                        exposed_attribute_labels[key_l] = (cfg.label or cfg.key or key_l)
                except Exception:
                    pass

                # Helper para normalizar categorías
                def _cat_to_dict(cat):
                    if isinstance(cat, dict):
                        return {
                            "id": cat.get("id"),
                            "name": cat.get("name"),
                            "name_en": cat.get("name_en"),
                            "slug": cat.get("slug")
                        }
                    return {
                        "id": getattr(cat, "id", None),
                        "name": getattr(cat, "name", None),
                        "name_en": getattr(cat, "name_en", None),
                        "slug": getattr(cat, "slug", None)
                    }

                # Si agrupamos, aplanar results_by_category en un array plano para el widget
                if group_by_category:
                    flattened_results = []
                    for cat_name, items in results_by_category.items():
                        flattened_results.extend(items)

                    response_data = {
                        "success": True,
                        "query": query_text,
                        "total_results": len(flattened_results),
                        "processing_time": round(elapsed, 3),
                        "group_by_category": group_by_category,
                        "results_by_category": results_by_category,
                        "results": flattened_results,  # Widget necesita esto poblado
                        "detection": {
                            "categorias_cliente_total": len(client_categories) if 'client_categories' in locals() else 0,
                            "categorias_matched": [_cat_to_dict(cat) for cat in (matched_categories or [])],
                            "tiene_match": len(matched_categories) > 0
                        },
                        "analysis": {
                            "atributos_configurados_total": len(configured_attributes) if 'configured_attributes' in locals() else 0,
                            "atributos_encontrados": atributos_encontrados or [],
                            "modificadores_no_configurados": modificadores_no_configurados or []
                        },
                        "exposed_attribute_keys": exposed_attribute_keys,
                        "exposed_attribute_labels": exposed_attribute_labels
                    }
                    print(f"📤 Retornando {len(flattened_results)} productos agrupados en {len(results_by_category)} categorías")
                else:
                    response_data = {
                        "success": True,
                        "query": query_text,
                        "total_results": len(formatted_results[:limit]),
                        "processing_time": round(elapsed, 3),
                        "group_by_category": False,
                        "results": formatted_results[:limit],
                        "detection": {
                            "categorias_cliente_total": len(client_categories) if 'client_categories' in locals() else 0,
                            "categorias_matched": [_cat_to_dict(cat) for cat in (matched_categories or [])],
                            "tiene_match": len(matched_categories) > 0
                        },
                        "analysis": {
                            "atributos_configurados_total": len(configured_attributes) if 'configured_attributes' in locals() else 0,
                            "atributos_encontrados": atributos_encontrados or [],
                            "modificadores_no_configurados": modificadores_no_configurados or []
                        },
                        "exposed_attribute_keys": exposed_attribute_keys,
                        "exposed_attribute_labels": exposed_attribute_labels
                    }
                    print(f"📤 Retornando {len(formatted_results[:limit])} productos sin agrupación")

                # 📊 También registrar analytics antes de retornar (evita perder conteo por early return)
                try:
                    import time as _t
                    print(f"🔍 ANALYTICS (early): Iniciando registro de búsqueda para client={client.id}", flush=True)
                    cats_detected = [ (c.get('name') if isinstance(c, dict) else getattr(c, 'name', None)) for c in (matched_categories or []) ]
                    cats_detected = [c for c in cats_detected if c]
                    cats_matched = list({(getattr(p.category, 'name', None) or '') for p in (filtered_products or []) if getattr(p, 'category', None)})
                    cats_matched = [c for c in cats_matched if c]
                    cats_missing = [c for c in cats_detected if c not in cats_matched]

                    # Fase 1: reglas claras de términos
                    # - terms_extracted: todos los modificadores extraídos del query
                    # - terms_matched: solo los modificadores que matchearon atributos (por key/label/valor)
                    # - terms_unmatched: modificadores que NO matchearon atributos
                    terms_extracted = [str(m).lower() for m in (modificadores or []) if str(m).strip()]
                    terms_matched = [
                        str(af.get('modificador_original')).lower()
                        for af in (atributos_encontrados or [])
                        if af.get('modificador_original')
                    ]
                    terms_unmatched = [str(m).lower() for m in (modificadores_no_configurados or []) if str(m).strip()]

                    had_results_flag = bool(filtered_products)

                    elapsed_ms = int(( _t.time() - start_time ) * 1000)
                    SearchLog.log_search(
                        client_id=client.id,
                        search_type='text',
                        query_text=query_text,
                        image_url=None,
                        categories_detected=cats_detected or None,
                        categories_matched=cats_matched or None,
                        categories_missing=cats_missing or None,
                        terms_extracted=terms_extracted or None,
                        terms_matched=terms_matched or None,
                        terms_unmatched=terms_unmatched or None,
                        results_count=len(filtered_products or []),
                        had_results=had_results_flag,
                        response_time_ms=elapsed_ms
                    )
                    print(f"✅ ANALYTICS (early): SearchLog.log_search() completado", flush=True)
                except Exception as _log_e:
                    import traceback as _tb
                    print(f"❌ ANALYTICS (early) ERROR: {_log_e}", flush=True)
                    print(f"   Traceback: {_tb.format_exc()}", flush=True)

                _resp = jsonify(response_data)
                _resp.headers['Access-Control-Allow-Origin'] = '*'
                _resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                _resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
                return _resp

            except Exception as e:
                attribute_keys = {}  # key normalizado -> objeto config
                attribute_labels = {}  # label normalizado -> objeto config

                # Evitar reclasificación si ya la hicimos exitosamente arriba
                if 'classification_done' in locals() and classification_done:
                    print("\n⚠️ Saltando reclasificación fallback (ya realizada previamente).")
                    # Omitir completamente la lógica de reclasificación duplicada
                    # (Evita contradicciones como perder match por valor 'negro')
                    # Continuar directamente hacia extracción de valores disponibles y retorno
                    # Preparar estructura mínima necesaria si no existe
                    if 'atributos_encontrados' not in locals():
                        atributos_encontrados = []
                    if 'modificadores_no_configurados' not in locals():
                        modificadores_no_configurados = []
                else:
                    # Solo ejecutar reclasificación si NO se realizó antes
                    print(f"\nAtributos configurados en el sistema ({len(configured_attributes)}):")
                    for attr in configured_attributes:
                        key_norm = attr.key.lower().strip()
                        label_norm = attr.label.lower().strip()
                        attribute_keys[key_norm] = attr
                        attribute_labels[label_norm] = attr
                        print(f"   - {attr.label} (key: '{attr.key}', type: {attr.type})")

                    # Analizar cada modificador (lógica corregida igual que bloque principal)
                    atributos_encontrados = []
                    modificadores_no_configurados = []

                    print(f"\n🔍 Comparando modificadores contra atributos configurados:")
                    for mod in modificadores:
                        mod_norm = mod.lower().strip()
                        matched = False
                        matched_config = None
                        match_type = None
                        matched_value = None

                        if mod_norm in attribute_keys:
                            matched = True
                            matched_config = attribute_keys[mod_norm]
                            match_type = 'key'
                        elif mod_norm in attribute_labels:
                            matched = True
                            matched_config = attribute_labels[mod_norm]
                            match_type = 'label'
                        else:
                            # Coincidencia por valor de atributos tipo list (corregido)
                            for cfg in configured_attributes:
                                if cfg.type == 'list' and cfg.options:
                                    try:
                                        import json, unicodedata as _ud
                                        raw_opt = cfg.options
                                        options = []
                                        if isinstance(raw_opt, list):
                                            options = raw_opt
                                        elif isinstance(raw_opt, dict):
                                            if 'values' in raw_opt and isinstance(raw_opt['values'], list):
                                                options = raw_opt['values']
                                            else:
                                                options = list(raw_opt.keys())
                                        elif isinstance(raw_opt, str):
                                            parsed = json.loads(raw_opt)
                                            if isinstance(parsed, list):
                                                options = parsed
                                            elif isinstance(parsed, dict):
                                                if 'values' in parsed and isinstance(parsed['values'], list):
                                                    options = parsed['values']
                                                else:
                                                    options = list(parsed.keys())
                                            else:
                                                continue
                                        else:
                                            continue

                                        def _norm_val(v):
                                            txt = str(v).strip().lower()
                                            txt = ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')
                                            return txt
                                        options_norm = [_norm_val(o) for o in options if str(o).strip()]

                                        if mod_norm in options_norm:
                                            matched = True
                                            matched_config = cfg
                                            match_type = 'value'
                                            matched_value = options[options_norm.index(mod_norm)]
                                            break
                                    except Exception:
                                        continue

                        if matched and matched_config:
                            info = {
                                'modificador_original': mod,
                                'atributo_key': matched_config.key,
                                'atributo_label': matched_config.label,
                                'atributo_type': matched_config.type,
                                'match_tipo': match_type
                            }
                            if match_type == 'value':
                                info['valor_detectado'] = matched_value
                                print(f"   ✅ '{mod}' → Match por valor de '{matched_config.label}' (key: {matched_config.key}, valor: {matched_value})")
                            else:
                                print(f"   ✅ '{mod}' → Atributo configurado: {matched_config.label} (key: {matched_config.key}, tipo: {match_type})")
                            atributos_encontrados.append(info)
                        else:
                            modificadores_no_configurados.append(mod)
                            print(f"   ❌ '{mod}' → NO es un atributo configurado")

                    classification_done = True

                    # Mostrar nuevamente resumen sólo si hubo reclasificación
                    print(f"\n📊 RESULTADO CLASIFICACIÓN (fallback):")
                    print(f"   ✅ Atributos encontrados: {len(atributos_encontrados)}")
                    print(f"   ❌ Modificadores NO configurados: {len(modificadores_no_configurados)}")

                # Saltar reclasificación duplicada: mantenemos resultado original
                # PASO 3: OBTENER VALORES DE ATRIBUTOS EN PRODUCTOS DE LAS CATEGORÍAS
                log_verbose(LogCategory.SEARCH, "="*60)
                print(f"📦 VALORES DE ATRIBUTOS EN PRODUCTOS")
                log_verbose(LogCategory.NLP, "="*60)

                atributos_valores_disponibles = {}  # key -> lista de valores únicos
                productos_analizados = 0

                if matched_category_ids:
                    _hang_trace(f"PRE-STAGE1: consultando productos por categorías matched={len(matched_category_ids)}")
                    # Query productos de las categorías detectadas
                    productos_en_categorias = Product.query.filter(
                        Product.client_id == client.id,
                        Product.category_id.in_(matched_category_ids),
                        Product.is_active == True
                    ).all()
                    _hang_trace(f"PRE-STAGE1: productos_en_categorias cargados={len(productos_en_categorias)}")

                    productos_analizados = len(productos_en_categorias)
                    print(f"Total productos en categorías detectadas: {productos_analizados}")

                    # Extraer valores únicos de cada atributo configurado
                    for attr_config in configured_attributes:
                        key = attr_config.key
                        valores_unicos = set()
                        _hang_trace(f"PRE-STAGE1: escaneando valores para atributo key='{key}'")

                        for producto in productos_en_categorias:
                            if producto.attributes and isinstance(producto.attributes, dict):
                                valor = producto.attributes.get(key)
                                if valor is not None and str(valor).strip():
                                    # Normalizar valor
                                    valor_str = str(valor).strip()
                                    valores_unicos.add(valor_str)

                        if valores_unicos:
                            atributos_valores_disponibles[key] = sorted(list(valores_unicos))
                            print(f"   {attr_config.label} ({key}): {len(valores_unicos)} valores únicos")
                            if len(valores_unicos) <= 5:
                                log_verbose(LogCategory.NLP, f"      Valores: {', '.join(sorted(list(valores_unicos)))}")
                            else:
                                log_verbose(LogCategory.NLP, f"      Valores: {', '.join(sorted(list(valores_unicos))[:5])} ...")

                    _hang_trace("PRE-STAGE1: extracción de valores por atributo finalizada")

                log_verbose(LogCategory.SEARCH, "="*60)
                log_verbose(LogCategory.CATEGORY_DETECTION, f"📊 RESUMEN FINAL")
                log_verbose(LogCategory.NLP, "="*60)
                print(f"✅ Atributos encontrados: {len(atributos_encontrados)}")
                for af in atributos_encontrados:
                    print(f"   - '{af['modificador_original']}' → {af['atributo_label']} ({af['atributo_key']})")

                print(f"\n❌ Modificadores NO configurados: {len(modificadores_no_configurados)}")
                for mnc in modificadores_no_configurados:
                    print(f"   - '{mnc}'")

                print(f"\n📦 Valores disponibles por atributo:")
                if atributos_valores_disponibles:
                    for key, valores in atributos_valores_disponibles.items():
                        label = next((a.label for a in configured_attributes if a.key == key), key)
                        print(f"   {label} ({key}): {valores}")
                else:
                    print(f"   (no hay datos en productos)")

                log_verbose(LogCategory.NLP, "="*60 + "\n")

                # Bloque de diagnóstico removido: continuar flujo normal de producción

            except Exception as e:
                if str(e) == "__SKIP_LEGACY_PRE_STAGE__":
                    pass
                else:
                    print(f"⚠️ Error en detección de categorías: {e}")
                    _hang_trace("PRE-STAGE1: excepción en bloque diagnóstico")
                    import traceback
                    traceback.print_exc()

            # (Bloque legacy removido para evitar problemas de comillas triple)

        else:
            # Si no pudimos extraer elementos, devolver banner de ayuda
            print(f"❌ [TEXT_SEARCH] Extractor devolvió vacío/None, mostrando banner de ayuda")
            response_data = {
                "success": True,
                "query": data.get('query', ''),
                "expanded_terms": [],
                "stage1_candidates": 0,
                "total_results": 0,
                "processing_time": round(time.time() - start_time, 3),
                "search_module": "generic",
                "user_feedback": {
                    "message": "Disculpá, no entendí lo que dijiste. Probá escribir solo el producto y color, por ejemplo: 'delantal verde' o 'top negro'.",
                    "has_results": False
                },
                "results": [],
                "results_by_category": {},
                "group_by_category": False
            }
            response = jsonify(response_data)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            return response

        log_verbose(LogCategory.SEARCH, "="*60)
        print(f"🔍 NUEVA BÚSQUEDA TEXTUAL V2")
        print(f"Query: '{query_text}' | Cliente: {client.name} | Limit: {limit}")
        log_verbose(LogCategory.NLP, "="*60)

        # Obtener slug del cliente para módulo personalizado
        client_slug = getattr(client, 'slug', None)

        # STAGE 1: Broad Recall (SQL) con delegación a módulo custom
        # 🔧 NO usamos lista hardcodeada - usamos get_system_color_adjectives() que carga del JSON
        try:
            from app.utils.semantic_colors import get_system_color_adjectives
            q_tokens_stage1 = {t.strip(".,;:!?").lower() for t in query_text.split() if t.strip()}
            system_colors = {str(c).strip().lower() for c in get_system_color_adjectives() if c}
            has_color_token = bool(q_tokens_stage1 & system_colors)
            print(f"🎨 Color detectado en query: {has_color_token}. Sistema colores totales: {len(system_colors)}")
        except Exception as e:
            print(f"⚠️ Error al cargar colores del sistema: {e}")
            has_color_token = False

        _hang_trace(f"PRE-STAGE1: invocando stage1_broad_recall has_color_token={has_color_token}")
        # Ahora le pasamos info de si es color para que stage1 decida el LIMIT
        candidates, detection_metadata = stage1_broad_recall(query_text, client.id, client_slug, is_color_search=has_color_token)
        _hang_trace(
            f"POST-STAGE1: candidates={len(candidates) if candidates is not None else -1}, "
            f"matched_categories={len(detection_metadata.get('matched_categories', [])) if detection_metadata else 0}"
        )

        # Guardar expanded_terms para la respuesta (ya se calculó en stage1)
        expanded_terms_cache = expand_query_with_synonyms(query_text, client.id, client_slug)

        # Si no se detecta categoría explícita, NO cortar: continuar con búsqueda amplia.
        no_explicit_category = not detection_metadata or not detection_metadata.get('matched_categories')
        available_names_for_guidance = []
        if no_explicit_category:
            try:
                available_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
                available_names_for_guidance = [cat.name for cat in available_categories]
            except Exception:
                available_names_for_guidance = []
            print("⚠️ [TEXT_SEARCH] Sin categoría explícita: se continúa en modo búsqueda amplia")

        if not candidates:
            if no_explicit_category:
                user_feedback = {
                    "message": "No detectamos una categoría exacta en tu descripción. Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda.",
                    "has_results": False,
                    "categories_available": available_names_for_guidance,
                    "suggestion": "Ejemplo: 'chaqueta azul para cocina' o 'delantal azul'."
                }
            else:
                # Si hay categoría válida pero no hay candidatos (caso raro)
                user_feedback = {
                    "message": "No se encontraron productos en las categorías detectadas.",
                    "has_results": False
                }
            response_data = {
                "success": True,
                "query": query_text,
                "expanded_terms": expanded_terms_cache,
                "stage1_candidates": 0,
                "total_results": 0,
                "processing_time": round(time.time() - start_time, 3),
                "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
                "user_feedback": user_feedback,
                "results": [],
                "results_by_category": {},
                "group_by_category": False,
                "categories_searched": available_names_for_guidance if no_explicit_category else []
            }
            response = jsonify(response_data)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            return response

        # Extraer atributos solicitados en la query (contexto del cliente)
        attr_info = extract_query_attributes(query_text, client.id)

        # 🟡 NUEVA LÓGICA: Inferir color semánticamente sin guardarlo en requested_attrs
        # Lo usaremos solo para calcular similares en el filtrado
        detected_color_token = None  # Token original que fue reconocido como color
        detected_color_normalized = None  # Color normalizado por LLM
        detected_color_intent = False  # Se detectó intención de color aunque no haya mapeo válido
        semantic_related_colors = []  # Colores relacionados desde definición sistémica
        color_detected_from_attr = False  # Color detectado a partir de intención extraída (LLM/extractor)

        try:
            requested_attrs = attr_info.get('attributes', {}) or {}
            not_configured_attrs = attr_info.get('not_configured', [])  # 🆕 Obtener atributos no configurados

            # 🆕 FILTRADO CRÍTICO: Excluir atributos no configurados de requested_attrs
            if not_configured_attrs:
                requested_attrs = {k: v for k, v in requested_attrs.items() if k.lower() not in [nc.lower() for nc in not_configured_attrs]}

            from app.utils.colors import normalize_color

            # Solo intentar normalizar tokens que NO sean categorías (evitar "delantal" → "bordo")
            category_tokens = set()
            try:
                categories = Category.query.filter_by(client_id=client.id).all()
                for cat in categories:
                    if cat.name:
                        category_tokens.update([t.lower() for t in cat.name.split()])
                    if hasattr(cat, 'alternative_terms') and cat.alternative_terms:
                        category_tokens.update([t.lower().strip() for t in cat.alternative_terms.split(',') if t.strip()])
            except Exception:
                pass

            # 🆕 Construir set de atributos configurados para excluir términos que sean atributos
            configured_attr_tokens = set()
            configured_color_values_norm = set()
            can_run_semantic_color = False
            try:
                from app.models.product_attribute_config import ProductAttributeConfig
                import json
                import ast
                import unicodedata as _ud_color

                def _norm_color_value(val):
                    txt = str(val or '').strip().lower()
                    return ''.join(ch for ch in _ud_color.normalize('NFD', txt) if _ud_color.category(ch) != 'Mn')

                configs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
                for cfg in configs:
                    key = (cfg.key or '').strip().lower()
                    if not key:
                        continue
                    # Extraer base del atributo (ej: 'con_bolsillo' → 'bolsillo')
                    if key.startswith('con_'):
                        base = key[4:]
                        configured_attr_tokens.add(base)
                        # Agregar plural común
                        configured_attr_tokens.add(base + 's')
                    configured_attr_tokens.add(key)

                    # Solo habilitar MiniLM de color si hay vocabulario de color real cargado
                    if 'color' in key:
                        raw_options = cfg.options
                        parsed_options = []
                        if isinstance(raw_options, list):
                            parsed_options = raw_options
                        elif isinstance(raw_options, dict):
                            if isinstance(raw_options.get('values'), list):
                                parsed_options = raw_options.get('values')
                            else:
                                parsed_options = list(raw_options.keys())
                        elif isinstance(raw_options, str) and raw_options.strip():
                            try:
                                decoded = json.loads(raw_options)
                            except Exception:
                                try:
                                    decoded = ast.literal_eval(raw_options)
                                except Exception:
                                    decoded = None

                            if isinstance(decoded, list):
                                parsed_options = decoded
                            elif isinstance(decoded, dict):
                                if isinstance(decoded.get('values'), list):
                                    parsed_options = decoded.get('values')
                                else:
                                    parsed_options = list(decoded.keys())

                        parsed_options = [str(v).strip() for v in parsed_options if str(v).strip()]
                        if parsed_options:
                            can_run_semantic_color = True
                            for opt in parsed_options:
                                norm_opt = _norm_color_value(opt)
                                if norm_opt:
                                    configured_color_values_norm.add(norm_opt)
            except Exception:
                pass

            raw_tokens = [t.strip(".,;:!?") for t in query_text.lower().split() if t.strip()]
            extracted_category_token = (extraction_result.get('category') or '').strip().lower()

            system_color_adjectives = set()
            try:
                from app.utils.semantic_colors import get_system_color_adjectives, _load_system_colors
                system_color_adjectives = {
                    str(c).strip().lower() for c in get_system_color_adjectives() if c
                }
            except Exception:
                # Fallback defensivo para mantener compatibilidad
                system_color_adjectives = {
                    str(c).strip().lower() for c in _NLP_CONFIG.get('color_adjectives', []) if c
                }

            # 🆕 CARGAR TOKENS EXCLUIDOS: Palabras que NO deben procesarse como colores
            excluded_color_tokens = set()
            require_adj_for_color = False
            try:
                sc_data = _load_system_colors()
                excluded_cfg = sc_data.get('excluded_tokens', {})
                if isinstance(excluded_cfg, dict):
                    for key, val in excluded_cfg.items():
                        if key == 'description' or key == 'min_token_length' or key == 'require_adj_pos':
                            continue
                        if isinstance(val, list):
                            excluded_color_tokens.update([str(t).strip().lower() for t in val if str(t).strip()])
                    require_adj_for_color = bool(excluded_cfg.get('require_adj_pos', False))
            except Exception as e:
                print(f"⚠️ Error cargando excluded_tokens: {e}")

            # Construir candidatos de color SIN hardcodear vocabulario:
            # 1) intención extraída por LLM/normalizador (attr_info['color'])
            # 2) términos útiles del extractor sintáctico
            # 3) fallback por POS (ADJ/NOUN/PROPN)
            requested_color_candidates = []
            requested_color_key = next(
                (k for k in requested_attrs.keys() if str(k).strip().lower() == 'color'),
                None
            )
            if requested_color_key and requested_attrs.get(requested_color_key) is not None:
                detected_color_intent = True
                raw_requested_color = requested_attrs.get(requested_color_key)
                raw_color_values = raw_requested_color if isinstance(raw_requested_color, list) else [raw_requested_color]
                for raw_val in raw_color_values:
                    if raw_val is None:
                        continue
                    txt = str(raw_val).strip().lower()
                    for part in txt.replace('/', ' ').replace(',', ' ').split():
                        token = part.strip(".,;:!?")
                        if token and token.isalpha() and len(token) >= 3:
                            requested_color_candidates.append(token)

            candidate_color_tokens = []
            for tok in requested_color_candidates:
                candidate_color_tokens.append((tok, 'attr'))

            for tok in extraction_result.get('modifiers', []) or []:
                tl = str(tok).strip().lower().strip(".,;:!?")
                if tl and tl.isalpha() and len(tl) >= 3:
                    candidate_color_tokens.append((tl, 'extractor'))

            for tok in (extraction_result.get('text', '') or '').split():
                tl = str(tok).strip().lower().strip(".,;:!?")
                if tl and tl.isalpha() and len(tl) >= 3:
                    candidate_color_tokens.append((tl, 'extractor'))

            try:
                nlp_for_color = _get_nlp_es()
                if nlp_for_color is not None:
                    doc_color = nlp_for_color(query_text)
                    for token in doc_color:
                        tl = token.text.lower().strip(".,;:!?")
                        if not tl or len(tl) < 3 or not tl.isalpha():
                            continue
                        if token.is_stop:
                            continue
                        if token.pos_ in ('ADJ', 'NOUN', 'PROPN'):
                            candidate_color_tokens.append((tl, 'nlp'))
            except Exception:
                pass

            # Dedupe preservando orden (por token)
            _seen_color_tokens = set()
            ordered_candidates = []
            for tok, source in candidate_color_tokens:
                if tok in _seen_color_tokens:
                    continue
                _seen_color_tokens.add(tok)
                ordered_candidates.append((tok, source))
            candidate_color_tokens = ordered_candidates

            if can_run_semantic_color:
                for tok, source in candidate_color_tokens:
                    if len(tok) < 3:
                        continue
                    # Saltar token de categoría principal extraída (evita normalizar color sobre categoría)
                    if extracted_category_token and tok == extracted_category_token:
                        continue
                    # Saltar si es una categoría conocida
                    if tok in category_tokens:
                        continue
                    # 🆕 Saltar si es un atributo configurado (evita interpretar "bolsillos" como color)
                    if tok in configured_attr_tokens:
                        continue
                    # 🆕🆕 Saltar si es un token excluido (pecho, cocina, color, etc - palabras que confunden)
                    if tok in excluded_color_tokens:
                        print(f"🚫 Token excluido (no es color): '{tok}'")
                        continue

                    # Coincidencia léxica directa contra opciones de color del cliente
                    tok_norm = tok
                    try:
                        import unicodedata as _ud_tok
                        tok_norm = ''.join(ch for ch in _ud_tok.normalize('NFD', tok) if _ud_tok.category(ch) != 'Mn')
                    except Exception:
                        tok_norm = tok
                    if tok_norm in configured_color_values_norm:
                        detected_color_intent = True
                        detected_color_token = tok
                        detected_color_normalized = tok_norm
                        color_detected_from_attr = (source == 'attr')
                        print(f"🎨 Color detectado (léxico cliente): '{tok}'")
                        break

                    # Marcar intención de color para adjetivos sistémicos aun si no hay mapeo
                    if tok in system_color_adjectives:
                        detected_color_intent = True
                        if not detected_color_token:
                            detected_color_token = tok

                        # Resolver relación definida en system_semantic_colors.json
                        try:
                            data_sc = _load_system_colors()
                            entries = data_sc.get('colors', []) if isinstance(data_sc, dict) else []
                            preferred = []
                            for item in entries:
                                if str(item.get('token', '')).strip().lower() == tok:
                                    preferred = [
                                        str(v).strip().lower()
                                        for v in item.get('preferred_matches', [])
                                        if str(v).strip()
                                    ]
                                    break

                            if preferred:
                                semantic_related_colors = list(dict.fromkeys(preferred))
                                detected_color_normalized = semantic_related_colors[0]
                                color_detected_from_attr = (source == 'attr')
                                print(f"🎨 Color sistémico detectado: '{tok}' -> familia {semantic_related_colors}")
                                # Para términos sistémicos, NO seguir normalización global por embedding
                                continue
                        except Exception as e_sc:
                            print(f"⚠️ Error leyendo definición sistémica para '{tok}': {e_sc}")

                    c = normalize_color(tok, client_id=client.id)
                    if c:
                        detected_color_intent = True
                        detected_color_token = tok
                        detected_color_normalized = c
                        color_detected_from_attr = (source == 'attr')
                        print(f"🎨 Color detectado (MiniLLM): '{tok}' → '{c}'")
                        break
            else:
                # Sin vocabulario de color utilizable, usar intención extraída por LLM/extractor.
                if requested_color_candidates:
                    detected_color_intent = True
                    detected_color_token = requested_color_candidates[0]
                    detected_color_normalized = requested_color_candidates[0]
                    color_detected_from_attr = True
                    print(f"🎨 Color detectado por intención extraída: '{detected_color_token}'")
                else:
                    print("🎨 Semántica de color omitida: cliente sin vocabulario de color utilizable")

            # NO agregamos a requested_attrs aquí - se manejará en el filtrado
        except Exception as _e:
            print(f"⚠️ Inferencia semántica de color falló: {_e}")

        # STAGE 2 NUEVO: construir frase CLIP (sustantivo + modificadores directos)
        # con normalización sistémica de color previa (ej. chocolate->marron).
        clip_query_text = _build_clip_query_from_extraction(
            extraction_result,
            client.id,
            detected_color_token=detected_color_token,
            detected_color_normalized=detected_color_normalized,
        )
        if not clip_query_text:
            # Fallback defensivo: usar query_text vigente si no pudo construirse frase.
            clip_query_text = query_text
        print(f"🧠 Frase CLIP final: '{clip_query_text}'")

        # Cuando hay intención explícita de color, ampliar el pool para que el filtro
        # posterior por embedding trabaje sobre más candidatos antes del corte final.
        if detected_color_intent:
            rerank_limit = min(len(candidates), max(limit * 10, 50)) if candidates else limit
        else:
            rerank_limit = limit
        scored_results = stage2_precise_rerank(clip_query_text, candidates, limit=rerank_limit)

        # Calcular cumplimiento de atributos por producto
        requested_attrs = attr_info.get('attributes', {})
        requested_attrs_confidence = attr_info.get('attributes_confidence', {}) or {}
        not_configured_attrs = attr_info.get('not_configured', [])  # 🆕 Obtener atributos no configurados

        # 🆕 FILTRADO CRÍTICO: Excluir atributos no configurados de requested_attrs
        # Si un atributo no está configurado en ProductAttributeConfig, NO lo usamos para filtrar
        # Esto permite que el sistema haga búsqueda semántica sin fallar por atributos ausentes
        if not_configured_attrs:
            requested_attrs = {k: v for k, v in requested_attrs.items() if k.lower() not in [nc.lower() for nc in not_configured_attrs]}
            requested_attrs_confidence = {
                k: v for k, v in requested_attrs_confidence.items()
                if str(k).lower() not in [nc.lower() for nc in not_configured_attrs]
            }
            log_verbose(LogCategory.SEARCH, f"🔄 Atributos no configurados excluidos: {not_configured_attrs}. Filtrando por: {list(requested_attrs.keys())}")

        requested_count = int(attr_info.get('requested_count', 0))
        # 🆕 Ajustar requested_count si hubo atributos excluidos
        requested_count = len(requested_attrs)

        # 🎨 NO agregamos detected_color_normalized a requested_attrs aquí
        # Lo manejaremos especialmente en el filtrado para buscar colores SIMILARES        # Formatear resultados
        formatted_results = []
        for result in scored_results:
            product = result['product']

            # Obtener imagen principal
            primary_image = Image.query.filter_by(
                product_id=product.id,
                is_primary=True
            ).first()

            if not primary_image:
                primary_image = Image.query.filter_by(
                    product_id=product.id
                ).first()

            # Atributos del producto
            prod_attrs = product.attributes or {}

            # Matching de atributos solicitados
            matched = {}
            for k, v in requested_attrs.items():
                pv = prod_attrs.get(k)
                if pv is None:
                    continue
                # soportalistas: si pv es lista
                if isinstance(pv, list):
                    if any(str(x).lower() == str(v).lower() for x in pv):
                        matched[k] = v
                else:
                    if str(pv).lower() == str(v).lower():
                        matched[k] = v

            matched_count = len(matched)
            match_ratio = float(matched_count / requested_count) if requested_count > 0 else 0.0

            # CRÍTICO: búsqueda de texto NO debe mutar imágenes/base64 en BD.
            # Este flujo debe ser estrictamente read-only.

            # Priorizar external_url (Tiendanube/externo) sobre url_producto (atributo custom)
            final_product_url = None
            if hasattr(product, 'external_url') and product.external_url:
                final_product_url = product.external_url
            elif prod_attrs.get('url_producto'):
                # Extraer de atributo JSONB si existe
                raw_url = prod_attrs.get('url_producto')
                if isinstance(raw_url, dict):
                    final_product_url = raw_url.get('value') or raw_url.get('url') or None
                else:
                    final_product_url = raw_url

            formatted_results.append({
                "id": product.id,
                "name": product.name,
                "price": float(product.price) if product.price is not None else None,
                "similarity": round(result['similarity'], 3),
                # Ordenamiento: primero por atributos cumplidos, luego por similitud
                # El widget usa final_score para badge. Mantenemos similitud y exponemos match_ratio aparte
                "final_score": round(result['similarity'], 3),
                "image": primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                "image_url": primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                "category": product.category.name if product.category else None,
                "attributes": prod_attrs,
                "attributes_matched": matched,
                "attributes_match_count": matched_count,
                "attributes_match_ratio": round(match_ratio, 3),
                "sku": product.sku,
                "stock": product.stock,
                "product_url": final_product_url  # URL para Tiendanube (prioriza external_url)
            })

        # RESPUESTA DIRECTA POST-STAGE2
        # Desactiva el filtrado/reordenamiento legacy posterior para preservar ranking CLIP.
        elapsed = time.time() - start_time
        results_by_category = {}
        group_by_category = False
        has_explicit_category = bool(detection_metadata and detection_metadata.get('matched_categories'))

        unique_categories = list(set(r.get('category') or 'Sin categoría' for r in formatted_results))
        should_group = has_explicit_category and len(unique_categories) > 1

        if should_group:
            group_by_category = True
            for row in formatted_results:
                cat = row.get('category') or 'Sin categoría'
                if cat not in results_by_category:
                    results_by_category[cat] = []
                if len(results_by_category[cat]) < per_category_limit:
                    results_by_category[cat].append(row)
            final_results = [item for items in results_by_category.values() for item in items]
        else:
            final_results = formatted_results[:limit]

        exposed_attribute_keys = []
        exposed_attribute_labels = {}
        try:
            from app.models.product_attribute_config import ProductAttributeConfig
            configs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            for cfg in configs:
                key_l = (cfg.key or '').strip().lower()
                if not key_l:
                    continue
                if cfg.expose_in_search:
                    exposed_attribute_keys.append(key_l)
                exposed_attribute_labels[key_l] = (cfg.label or cfg.key or key_l)
        except Exception:
            pass

        response_data = {
            "success": True,
            "query": query_text,
            "expanded_terms": expanded_terms_cache,
            "stage1_candidates": len(candidates),
            "total_results": len(final_results),
            "processing_time": round(elapsed, 3),
            "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
            "user_feedback": user_feedback,
            "group_by_category": group_by_category,
            "categories_searched": user_feedback.get('categories_shown') or available_names_for_guidance,
            "exposed_attribute_keys": exposed_attribute_keys,
            "exposed_attribute_labels": exposed_attribute_labels
        }

        if group_by_category:
            response_data["results_by_category"] = results_by_category
            response_data["results"] = []
        else:
            response_data["results"] = final_results

        response = jsonify(response_data)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        return response

        # IMPORTANTE: conservar la intención explícita de atributos/color para el
        # ranking final. Si se limpia aquí, se pierde la priorización solicitada
        # por el usuario (ej: "azul", "manga corta").

        # 🔍 FILTRADO POR ATRIBUTOS SOLICITADOS (LEGACY)
        # Si se solicitaron atributos, mostrar productos que cumplan:
        # - Si se pidió color: preferir coincidencia estricta por color
        # - En caso contrario: al menos 1 atributo solicitado
        resolved_color_cache = {}

        def _extract_scalar_color_value(raw_value):
            if raw_value is None:
                return None
            if isinstance(raw_value, dict):
                return raw_value.get('value') or raw_value.get('label') or raw_value.get('name')
            if isinstance(raw_value, list) and raw_value:
                first_val = raw_value[0]
                if isinstance(first_val, dict):
                    return first_val.get('value') or first_val.get('label') or first_val.get('name')
                return first_val
            if isinstance(raw_value, str):
                txt = raw_value.strip()
                if txt.startswith('[') and txt.endswith(']'):
                    try:
                        import ast
                        parsed = ast.literal_eval(txt)
                        if isinstance(parsed, list) and parsed:
                            return parsed[0]
                    except Exception:
                        pass
                return txt
            return raw_value

        color_text_matrix = None
        color_keys = [
            'negro', 'blanco', 'gris', 'azul', 'celeste', 'verde', 'rojo',
            'rosa', 'marron', 'beige', 'amarillo', 'violeta', 'naranja'
        ]
        color_prompt_names = {
            'negro': 'black', 'blanco': 'white', 'gris': 'gray', 'azul': 'blue',
            'celeste': 'light blue', 'verde': 'green', 'rojo': 'red', 'rosa': 'pink',
            'marron': 'brown', 'beige': 'beige', 'amarillo': 'yellow',
            'violeta': 'purple', 'naranja': 'orange'
        }

        configured_color_keys = ['color']
        _hang_trace("INIT color pipeline: cargando configured_color_keys")
        try:
            from app.models.product_attribute_config import ProductAttributeConfig
            cfgs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            exact_color_keys = [
                (cfg.key or '').strip().lower()
                for cfg in cfgs
                if (cfg.key or '').strip().lower() == 'color'
            ]
            if exact_color_keys:
                configured_color_keys = exact_color_keys
            else:
                contains_color_keys = [
                    (cfg.key or '').strip().lower()
                    for cfg in cfgs
                    if 'color' in (cfg.key or '').strip().lower()
                ]
                if contains_color_keys:
                    configured_color_keys = contains_color_keys
        except Exception:
            pass
        _hang_trace(f"configured_color_keys={configured_color_keys}")

        color_resolve_stats = {
            'calls': 0,
            'cache_hits': 0,
            'cache_miss': 0,
        }
        color_visual_score_cache = {}
        strict_color_min_score = 0.25

        def _get_color_family_keys(target_color):
            target_norm = str(target_color or '').strip().lower()
            target_aliases = {
                'azul': ['azul', 'celeste'],
                'celeste': ['celeste', 'azul'],
                'marron': ['marron', 'beige'],
                'marrón': ['marron', 'beige'],
            }
            return target_aliases.get(target_norm, [target_norm])

        def _infer_color_from_product_embedding(product_id):
            nonlocal color_text_matrix
            try:
                primary_image = Image.query.filter_by(product_id=product_id, is_primary=True).first()
                if not primary_image:
                    primary_image = Image.query.filter_by(product_id=product_id).first()
                if not primary_image or not primary_image.embedding_vector:
                    return None

                emb = np.asarray(primary_image.embedding_vector, dtype=np.float32)
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    return None
                emb = emb / emb_norm

                if color_text_matrix is None:
                    clip_model, clip_processor = get_clip_model()
                    prompts = [f"a photo of a {color_prompt_names[k]} garment" for k in color_keys]
                    with torch.no_grad():
                        text_inputs = clip_processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
                        text_features = clip_model.get_text_features(**text_inputs)
                        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                        color_text_matrix = text_features.cpu().numpy().astype(np.float32)

                sims = np.dot(color_text_matrix, emb)
                best_idx = int(np.argmax(sims))
                best_sim = float(sims[best_idx])
                second_sim = float(np.partition(sims, -2)[-2]) if len(sims) > 1 else -1.0

                # Requerir confianza mínima para evitar asignaciones espurias
                # sobre imágenes sin color dominante claro.
                min_sim = 0.24
                min_margin = 0.02
                if best_sim < min_sim or (best_sim - second_sim) < min_margin:
                    return None

                return color_keys[best_idx]
            except Exception:
                return None

        def _get_product_color_similarity(product_id, target_color):
            nonlocal color_text_matrix
            cache_key = f"{product_id}:{str(target_color).strip().lower()}"
            if cache_key in color_visual_score_cache:
                return color_visual_score_cache[cache_key]

            try:
                primary_image = Image.query.filter_by(product_id=product_id, is_primary=True).first()
                if not primary_image:
                    primary_image = Image.query.filter_by(product_id=product_id).first()
                if not primary_image or not primary_image.embedding_vector:
                    color_visual_score_cache[cache_key] = 0.0
                    return 0.0

                emb = np.asarray(primary_image.embedding_vector, dtype=np.float32)
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    color_visual_score_cache[cache_key] = 0.0
                    return 0.0
                emb = emb / emb_norm

                if color_text_matrix is None:
                    clip_model, clip_processor = get_clip_model()
                    prompts = [f"a photo of a {color_prompt_names[k]} garment" for k in color_keys]
                    with torch.no_grad():
                        text_inputs = clip_processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
                        text_features = clip_model.get_text_features(**text_inputs)
                        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                        color_text_matrix = text_features.cpu().numpy().astype(np.float32)

                target_norm = str(target_color or '').strip().lower()
                candidate_keys = _get_color_family_keys(target_norm)
                candidate_indexes = [idx for idx, key in enumerate(color_keys) if key in candidate_keys]
                if not candidate_indexes:
                    candidate_indexes = [idx for idx, key in enumerate(color_keys) if key == target_norm]
                if not candidate_indexes:
                    color_visual_score_cache[cache_key] = 0.0
                    return 0.0

                sims = np.dot(color_text_matrix, emb)
                score = max(float(sims[idx]) for idx in candidate_indexes)
                score = max(0.0, min(0.99, score))
                color_visual_score_cache[cache_key] = score
                return score
            except Exception:
                color_visual_score_cache[cache_key] = 0.0
                return 0.0

        def _resolve_product_color_norm(result_row):
            color_resolve_stats['calls'] += 1
            result_id = result_row.get('id')
            cache_key = str(result_id)
            if cache_key in resolved_color_cache:
                color_resolve_stats['cache_hits'] += 1
                return resolved_color_cache[cache_key]

            color_resolve_stats['cache_miss'] += 1
            if color_resolve_stats['cache_miss'] <= 5:
                _hang_trace(f"resolve_color miss product_id={result_id}")

            product_attrs = result_row.get('attributes') or {}
            attrs_lower = {str(k).strip().lower(): v for k, v in product_attrs.items()}

            resolved = None

            # 1) Atributo configurado
            for ck in configured_color_keys:
                if ck in attrs_lower:
                    raw_attr_color = _extract_scalar_color_value(attrs_lower.get(ck))
                    if raw_attr_color:
                        resolved = normalize_color(str(raw_attr_color), client_id=client.id)
                        if resolved:
                            break

            # 2) CLIP embedding de imagen
            if not resolved:
                resolved = _infer_color_from_product_embedding(result_id)

            # 3) Fallback léxico por familia semántica (atributos/nombre) cuando hay intención de color
            if not resolved and detected_color_intent and semantic_related_colors:
                related_set = {
                    str(v).strip().lower()
                    for v in semantic_related_colors
                    if str(v).strip()
                }

                # Buscar en cualquier atributo textual del producto
                for raw_v in attrs_lower.values():
                    raw_txt = str(_extract_scalar_color_value(raw_v) or raw_v).strip().lower()
                    if raw_txt and (raw_txt in related_set or any(rel in raw_txt for rel in related_set)):
                        resolved = next((rel for rel in related_set if rel in raw_txt), raw_txt)
                        break

                # Buscar en nombre del producto
                if not resolved:
                    name_txt = str(result_row.get('name') or '').strip().lower()
                    if name_txt:
                        hit = next((rel for rel in related_set if rel in name_txt), None)
                        if hit:
                            resolved = hit

            # 4) NO inferir color por nombre de producto aquí:
            # evita falsos positivos semánticos (ej: "food" -> "sushi").

            resolved_color_cache[cache_key] = resolved
            if color_resolve_stats['cache_miss'] <= 5:
                _hang_trace(f"resolve_color result product_id={result_id} -> {resolved}")
            return resolved

        def _build_color_priority_score_fn(requested_attrs_dict, detected_color_norm, strict_exact_match=False):
            if not color_priority_enabled:
                return (lambda _r: 0.0), None

            target_color = None
            try:
                color_req_key_local = next(
                    (k for k in requested_attrs_dict.keys() if str(k).strip().lower() == 'color'),
                    None
                )
                if color_req_key_local and requested_attrs_dict.get(color_req_key_local):
                    target_color = str(requested_attrs_dict.get(color_req_key_local)).strip().lower()
                elif detected_color_norm:
                    target_color = str(detected_color_norm).strip().lower()
            except Exception:
                target_color = None

            if not target_color:
                return (lambda _r: 0.0), None

            try:
                from app.utils.colors import _get_color_embedding
                target_emb_local = _get_color_embedding(target_color, client_id=client.id)
            except Exception:
                target_emb_local = None

            sim_cache = {}

            def _score(row):
                try:
                    if strict_exact_match:
                        resolved_color = _resolve_product_color_norm(row)
                        if resolved_color:
                            resolved_norm = str(resolved_color).strip().lower()
                            if resolved_norm == target_color:
                                return 1.0
                        visual_score = _get_product_color_similarity(row.get('id'), target_color)
                        if visual_score < strict_color_min_score:
                            return 0.0
                        # Reescalar score estricto para que similitudes bajas no compitan con matches reales.
                        return (visual_score - strict_color_min_score) / max(1e-6, (0.99 - strict_color_min_score))

                    resolved_color = _resolve_product_color_norm(row)
                    if not resolved_color:
                        return 0.0
                    resolved_norm = str(resolved_color).strip().lower()
                    if resolved_norm == target_color:
                        return 1.0
                    if target_emb_local is None:
                        return 0.0
                    if resolved_norm in sim_cache:
                        return sim_cache[resolved_norm]

                    emb_color = _get_color_embedding(resolved_norm, client_id=client.id)
                    if emb_color is None:
                        sim_cache[resolved_norm] = 0.0
                        return 0.0

                    denom = (np.linalg.norm(target_emb_local) * np.linalg.norm(emb_color))
                    if denom == 0:
                        sim_cache[resolved_norm] = 0.0
                        return 0.0

                    sim_val = float(np.dot(target_emb_local, emb_color) / denom)
                    sim_val = max(0.0, min(0.99, sim_val))
                    sim_cache[resolved_norm] = sim_val
                    return sim_val
                except Exception:
                    return 0.0

            return _score, target_color

        def _build_attribute_priority_score_fn(requested_attrs_dict, attrs_confidence_dict):
            """Crea un score dinamico (0-1) segun atributos explicitamente pedidos."""
            if not isinstance(requested_attrs_dict, dict) or not requested_attrs_dict:
                return (lambda _r: 0.0), {}

            import unicodedata as _ud

            def _norm_txt(value):
                if value is None:
                    return ''
                txt = str(value).strip().lower()
                return ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')

            def _to_norm_list(value):
                if value is None:
                    return []
                raw_vals = []
                if isinstance(value, list):
                    raw_vals = value
                elif isinstance(value, dict):
                    raw_vals = [value.get('value') or value.get('label') or value.get('name')]
                else:
                    raw_vals = [value]
                return [_norm_txt(v) for v in raw_vals if str(v).strip()]

            requested_by_key = {}
            for key, value in requested_attrs_dict.items():
                k_norm = _norm_txt(key)
                if not k_norm:
                    continue
                requested_by_key[k_norm] = value

            if not requested_by_key:
                return (lambda _r: 0.0), {}

            confidence_lookup = {}
            if isinstance(attrs_confidence_dict, dict):
                for key, value in attrs_confidence_dict.items():
                    confidence_lookup[_norm_txt(key)] = _norm_txt(value)

            # Ponderacion generica por calidad de deteccion (no depende de keys hardcodeadas)
            confidence_weight = {
                'boolean': 1.20,
                'lexical': 1.15,
                'semantic': 1.00,
            }

            weights = {}
            requested_values_norm = {}
            for key_norm, req_value in requested_by_key.items():
                conf = confidence_lookup.get(key_norm, '')
                weights[key_norm] = confidence_weight.get(conf, 1.0)
                requested_values_norm[key_norm] = set(_to_norm_list(req_value))

            total_weight = sum(weights.values()) or 1.0

            def _score(row):
                try:
                    attrs_raw = row.get('attributes') or {}
                    attrs_by_key = {
                        _norm_txt(k): v for k, v in attrs_raw.items()
                    } if isinstance(attrs_raw, dict) else {}

                    matched_raw = row.get('attributes_matched') or {}
                    matched_keys = {_norm_txt(k) for k in matched_raw.keys()}

                    matched_weight = 0.0
                    for key_norm, req_values in requested_values_norm.items():
                        is_match = False

                        if key_norm in matched_keys:
                            is_match = True
                        else:
                            prod_value = attrs_by_key.get(key_norm)
                            if prod_value is not None:
                                prod_values_norm = _to_norm_list(prod_value)
                                if not req_values:
                                    is_match = bool(prod_values_norm)
                                else:
                                    for pv in prod_values_norm:
                                        if pv in req_values:
                                            is_match = True
                                            break
                                        if pv.endswith('s') and pv[:-1] in req_values:
                                            is_match = True
                                            break
                        if is_match:
                            matched_weight += weights.get(key_norm, 1.0)

                    return max(0.0, min(1.0, matched_weight / total_weight))
                except Exception:
                    return 0.0

            return _score, weights

        if requested_count > 0 or detected_color_normalized or detected_color_intent:
            _hang_trace(
                f"ENTER filter branch requested_count={requested_count}, "
                f"detected_color_normalized={detected_color_normalized}, detected_color_intent={detected_color_intent}, "
                f"formatted_results={len(formatted_results)}"
            )
            # Antes de filtrar, recopilar todos los valores disponibles para cada atributo solicitado
            all_available_values = {}
            for attr_key in requested_attrs.keys():
                available_vals = set()
                for r in formatted_results:
                    prod_attrs = r.get('attributes', {})
                    val = prod_attrs.get(attr_key)
                    if val is not None:
                        if isinstance(val, list):
                            for v in val:
                                available_vals.add(str(v))
                        else:
                            available_vals.add(str(val))
                all_available_values[attr_key] = sorted(list(available_vals))

            # Si se solicitó color o si detectamos color por normalización, filtrar por coincidencia
            color_req_key = next((k for k in requested_attrs.keys() if str(k).lower() == 'color'), None)

            # 🎨 Variable para guardar el color similar encontrado (para matching posterior)
            matched_similar_color = None

            filtered_results = []
            # Determinar valor de color a filtrar (desde requested o desde detección)
            color_filter_value = None
            if color_req_key:
                requested_color_value = str(requested_attrs.get(color_req_key, '')).lower()
                requested_color_conf = str(requested_attrs_confidence.get(color_req_key, '')).lower()
                if color_detected_from_attr and detected_color_normalized:
                    color_filter_value = str(detected_color_normalized).lower()
                    requested_attrs[color_req_key] = color_filter_value
                elif requested_color_conf == 'semantic' and detected_color_normalized:
                    color_filter_value = str(detected_color_normalized).lower()
                    requested_attrs[color_req_key] = color_filter_value
                else:
                    color_filter_value = requested_color_value
            elif detected_color_normalized:
                color_filter_value = str(detected_color_normalized).lower()

            if color_filter_value:
                _hang_trace(f"color_filter_value='{color_filter_value}' token='{detected_color_token}'")
                pre_color_results = list(formatted_results)
                color_search_token = detected_color_token if detected_color_token else color_filter_value
                color_value_normalized = color_filter_value
                # Color base: si viene de definición sistémica, usar su familia; si no, el color normalizado.
                base_colors = [color_value_normalized]
                if semantic_related_colors:
                    merged_base = [color_value_normalized] + [str(v).strip().lower() for v in semantic_related_colors if str(v).strip()]
                    base_colors = list(dict.fromkeys([c for c in merged_base if c]))

                base_set = set(base_colors)
                base_anchor = base_colors[0] if base_colors else color_value_normalized
                print(f"🎨 Filtrando por color: token='{color_search_token}', base={base_colors}")

                alias_map = {
                    'azul': {'azul', 'celeste', 'marino', 'navy', 'blue'},
                    'celeste': {'celeste', 'azul', 'marino', 'navy'},
                    'marron': {'marron', 'marrón', 'brown', 'habano', 'tostado', 'camel', 'caramelo', 'beige', 'baige', 'tierra', 'terra'},
                    'marrón': {'marron', 'marrón', 'brown', 'habano', 'tostado', 'camel', 'caramelo', 'beige', 'baige', 'tierra', 'terra'},
                }
                exact_color_visual_threshold = strict_color_min_score

                backfill_tokens = set(base_set)
                for bc in list(base_set):
                    backfill_tokens.update(alias_map.get(str(bc).strip().lower(), set()))

                def _row_text_for_color_backfill(row) -> str:
                    attrs = row.get('attributes') or {}
                    attrs_txt = []
                    if isinstance(attrs, dict):
                        for v in attrs.values():
                            vv = _extract_scalar_color_value(v)
                            if vv is None:
                                vv = v
                            attrs_txt.append(str(vv))
                    return (str(row.get('name') or '') + ' ' + ' '.join(attrs_txt)).strip().lower()

                def _product_matches_base_colors(row) -> bool:
                    # 1) atributo JSON configurado
                    attrs_raw = row.get('attributes') or {}
                    attrs_lower = {str(k).strip().lower(): v for k, v in attrs_raw.items()} if isinstance(attrs_raw, dict) else {}
                    for ck in configured_color_keys:
                        if ck in attrs_lower:
                            raw_attr = _extract_scalar_color_value(attrs_lower.get(ck))
                            if raw_attr:
                                norm_attr = normalize_color(str(raw_attr), client_id=client.id)
                                candidate_attr = (norm_attr or str(raw_attr)).strip().lower()
                                if candidate_attr in base_set or any(b in candidate_attr for b in base_set):
                                    return True

                    # 2) embedding de imagen por score continuo de familia, no por top-1.
                    visual_score = _get_product_color_similarity(row.get('id'), base_anchor)
                    if visual_score >= exact_color_visual_threshold:
                        return True

                    # 3) nombre de producto
                    name_txt = str(row.get('name') or '').strip().lower()
                    if name_txt and any(tok in name_txt for tok in backfill_tokens):
                        return True

                    return False

                # 1) Exactos primero (color base/familia)
                filtered_results = [
                    r for r in formatted_results
                    if _product_matches_base_colors(r)
                ]
                _hang_trace(f"exact/base color matches={len(filtered_results)}")

                # 2) Si faltan resultados, completar con colores similares
                try:
                    target_total = limit
                    target_total = min(target_total, len(pre_color_results))
                except Exception:
                    target_total = limit

                if len(filtered_results) < target_total:
                    strict_color_search = bool(detected_color_token)
                    if strict_color_search:
                        print(
                            f"🔍 Exactos insuficientes ({len(filtered_results)}/{target_total}), "
                            f"manteniendo búsqueda estricta para '{base_anchor}' por CLIP/léxico..."
                        )
                    else:
                        print(f"🔍 Exactos insuficientes ({len(filtered_results)}/{target_total}), buscando colores similares a '{base_anchor}'...")
                    try:
                        if strict_color_search and len(filtered_results) < target_total:
                            visual_candidates = []
                            for r in pre_color_results:
                                if r in filtered_results:
                                    continue
                                visual_score = _get_product_color_similarity(r.get('id'), base_anchor)
                                visual_candidates.append((r, visual_score))

                            visual_candidates.sort(key=lambda item: item[1], reverse=True)
                            print(
                                f"🎨 Top score visual '{base_anchor}': "
                                f"{[(item[0].get('name'), round(item[1], 3)) for item in visual_candidates[:5]]}"
                            )

                            min_visual_score = strict_color_min_score
                            for row, visual_score in visual_candidates:
                                if visual_score < min_visual_score:
                                    continue
                                filtered_results.append(row)
                                if len(filtered_results) >= target_total:
                                    break

                        if not strict_color_search:
                            from app.utils.colors import _get_color_embedding
                            target_emb = _get_color_embedding(base_anchor, client_id=client.id)
                            similar_colors = []

                            if target_emb is not None:
                                available_product_colors = [
                                    _resolve_product_color_norm(r)
                                    for r in pre_color_results
                                ]
                                available_product_colors = [c for c in available_product_colors if c]
                                scored = []
                                for c in set(available_product_colors):
                                    if c in base_set:
                                        continue
                                    emb_c = _get_color_embedding(c, client_id=client.id)
                                    if emb_c is None:
                                        continue
                                    denom = (np.linalg.norm(target_emb) * np.linalg.norm(emb_c))
                                    if denom == 0:
                                        continue
                                    sim = float(np.dot(target_emb, emb_c) / denom)
                                    scored.append((c, sim))

                                scored.sort(key=lambda x: x[1], reverse=True)
                                THRESH = 0.50
                                TOPK = 4
                                similar_colors = [c for c, s in scored if s >= THRESH][:TOPK]
                                if not similar_colors:
                                    THRESH = 0.35
                                    similar_colors = [c for c, s in scored if s >= THRESH][:TOPK]
                                print(f"🎨 Similares a '{base_anchor}': {[(c, round(s,3)) for c,s in scored[:5]]}")
                                print(f"✅ Top similares (>{THRESH}): {similar_colors}")

                            if similar_colors:
                                similar_set = set(similar_colors)
                                for r in pre_color_results:
                                    if r in filtered_results:
                                        continue
                                    rc = _resolve_product_color_norm(r)
                                    if rc in similar_set:
                                        filtered_results.append(r)
                                    if len(filtered_results) >= target_total:
                                        break

                        # Backfill léxico: si aún faltan resultados, completar por términos de color en nombre/atributos.
                        if len(filtered_results) < target_total:
                            for r in pre_color_results:
                                if r in filtered_results:
                                    continue
                                row_txt = _row_text_for_color_backfill(r)
                                if row_txt and any(tok in row_txt for tok in backfill_tokens):
                                    filtered_results.append(r)
                                if len(filtered_results) >= target_total:
                                    break

                        # No reducir cantidad de resultados por un filtro de color incompleto:
                        # si faltan items para el límite, completar con el resto del top original.
                        if len(filtered_results) < target_total:
                            for r in pre_color_results:
                                if r in filtered_results:
                                    continue
                                filtered_results.append(r)
                                if len(filtered_results) >= target_total:
                                    break
                    except Exception as e:
                        print(f"⚠️ Error buscando colores similares: {e}")

                # Fijar color final usado en matching/feedback
                matched_similar_color = base_anchor
                requested_attrs['color'] = matched_similar_color
                detected_color_normalized = matched_similar_color
                print(f"🎨 Color para matching fijado: '{matched_similar_color}'")

                # Recalcular métricas de atributos
                for r in filtered_results:
                    prod_attrs = r.get('attributes', {})
                    matched = {}
                    for k, v in requested_attrs.items():
                        pv = prod_attrs.get(k)
                        if pv is None:
                            if str(k).lower() == 'color':
                                pv = _resolve_product_color_norm(r)
                                if pv is None:
                                    continue
                            else:
                                continue
                        if str(k).lower() == 'color':
                            if str(pv).lower() in base_set:
                                matched[k] = matched_similar_color
                            continue
                        if isinstance(pv, list):
                            if any(str(x).lower() == str(v).lower() for x in pv):
                                matched[k] = v
                        else:
                            if str(pv).lower() == str(v).lower():
                                matched[k] = v

                    matched_count = len(matched)
                    match_ratio = float(matched_count / len(requested_attrs)) if len(requested_attrs) > 0 else 0.0
                    r['attributes_matched'] = matched
                    r['attributes_match_count'] = matched_count
                    r['attributes_match_ratio'] = round(match_ratio, 3)

                formatted_results = filtered_results
                if base_colors:
                    all_available_values['color'] = base_colors
                _hang_trace(f"after unified color branch formatted_results={len(formatted_results)}")
            else:
                _hang_trace("ENTER no-color-filter branch")
                # Si hubo intención explícita de color pero no se pudo normalizar/matchear,
                # intentar resolver color objetivo por similitud CLIP sobre candidatos.
                if detected_color_intent:
                    _hang_trace("detected_color_intent=True -> start recovered_color flow")
                    recovered_color = None
                    preferred_matches_for_token = []
                    try:
                        from app.utils.colors import _get_color_embedding
                        from app.utils.semantic_colors import _load_system_colors
                        search_token = detected_color_token or query_text
                        target_emb = _get_color_embedding(str(search_token), client_id=client.id)
                        available_product_colors = [
                            _resolve_product_color_norm(r)
                            for r in formatted_results
                        ]
                        available_product_colors = [c for c in available_product_colors if c]
                        _hang_trace(f"recovered_color flow: available_product_colors={len(available_product_colors)}")

                        # 1) Priorizar matches léxicos declarados en configuración semántica
                        #    (ej: chocolate -> familia marrón) si existen en candidatos.
                        if available_product_colors and detected_color_token:
                            try:
                                data_sc = _load_system_colors()
                                entries = data_sc.get('colors', []) if isinstance(data_sc, dict) else []
                                token_norm = str(detected_color_token).strip().lower()
                                preferred = []
                                for item in entries:
                                    tok = str(item.get('token', '')).strip().lower()
                                    if tok == token_norm:
                                        preferred = [str(v).strip().lower() for v in item.get('preferred_matches', []) if str(v).strip()]
                                        preferred_matches_for_token = list(preferred)
                                        break
                                if preferred:
                                    available_unique = list(dict.fromkeys(available_product_colors))
                                    lexical_hits = [
                                        c for c in available_unique
                                        if any(p in str(c).lower() for p in preferred)
                                    ]
                                    if lexical_hits:
                                        recovered_color = lexical_hits[0]
                                        print(f"🎨 Recuperación color léxica: token='{search_token}' → '{recovered_color}'")
                                        _hang_trace(f"recovered_color lexical={recovered_color}")
                            except Exception as e_pref:
                                print(f"⚠️ Recuperación léxica por preferred_matches falló: {e_pref}")

                        # 2) Fallback por similitud CLIP con umbral mínimo de confianza.
                        if recovered_color is None and target_emb is not None and available_product_colors:
                            scored = []
                            for c in set(available_product_colors):
                                emb_c = _get_color_embedding(c, client_id=client.id)
                                if emb_c is None:
                                    continue
                                denom = (np.linalg.norm(target_emb) * np.linalg.norm(emb_c))
                                if denom == 0:
                                    continue
                                sim = float(np.dot(target_emb, emb_c) / denom)
                                scored.append((c, sim))

                            scored.sort(key=lambda x: x[1], reverse=True)
                            if scored:
                                best_color, best_sim = scored[0]
                                if best_sim >= 0.50:
                                    recovered_color = best_color
                                    print(f"🎨 Recuperación color por CLIP: token='{search_token}' → '{recovered_color}' (sim={best_sim:.3f})")
                                    _hang_trace(f"recovered_color clip={recovered_color} sim={best_sim:.3f}")
                                else:
                                    print(f"🎨 Recuperación color CLIP descartada por baja similitud: top='{best_color}' sim={best_sim:.3f}")
                                    _hang_trace(f"recovered_color clip discarded sim={best_sim:.3f}")

                    except Exception as e_recover:
                        print(f"⚠️ Recuperación de color por CLIP falló: {e_recover}")

                    if recovered_color:
                        _hang_trace(f"apply recovered_color={recovered_color}")
                        detected_color_normalized = recovered_color
                        color_filter_value = recovered_color
                        pre_color_results = list(formatted_results)
                        try:
                            from app.utils.colors import _get_color_embedding
                            target_emb_local = _get_color_embedding(str(recovered_color), client_id=client.id)
                            emb_cache_local = {}

                            preferred_set = {
                                str(v).strip().lower()
                                for v in ([recovered_color] + (preferred_matches_for_token or []))
                                if str(v).strip()
                            }

                            def _matches_target_family(color_value: str) -> bool:
                                if not color_value:
                                    return False
                                norm_val = str(color_value).strip().lower()
                                if norm_val == recovered_color:
                                    return True
                                if norm_val in preferred_set:
                                    return True
                                if any(pref in norm_val for pref in preferred_set):
                                    return True
                                return _is_close_color(norm_val)

                            def _is_close_color(candidate_color: str) -> bool:
                                if not target_emb_local or not candidate_color:
                                    return False
                                cand_norm = str(candidate_color).strip().lower()
                                if cand_norm in emb_cache_local:
                                    emb_c = emb_cache_local[cand_norm]
                                else:
                                    emb_c = _get_color_embedding(cand_norm, client_id=client.id)
                                    emb_cache_local[cand_norm] = emb_c
                                if emb_c is None:
                                    return False
                                denom = (np.linalg.norm(target_emb_local) * np.linalg.norm(emb_c))
                                if denom == 0:
                                    return False
                                sim = float(np.dot(target_emb_local, emb_c) / denom)
                                return sim >= 0.64

                            filtered_results = []
                            existing_ids = set()
                            for r in formatted_results:
                                rid = str(r.get('id')) if r.get('id') is not None else None
                                if rid and rid in existing_ids:
                                    continue

                                # 1) Prioridad: atributo JSON de color
                                attrs_raw = r.get('attributes') or {}
                                attrs_lower = {str(k).strip().lower(): v for k, v in attrs_raw.items()} if isinstance(attrs_raw, dict) else {}
                                attr_color_match = None
                                for ck in configured_color_keys:
                                    if ck in attrs_lower:
                                        raw_attr = _extract_scalar_color_value(attrs_lower.get(ck))
                                        if raw_attr:
                                            norm_attr = normalize_color(str(raw_attr), client_id=client.id)
                                            candidate_attr = norm_attr or str(raw_attr).strip().lower()
                                            if _matches_target_family(candidate_attr):
                                                attr_color_match = candidate_attr
                                                break
                                if attr_color_match:
                                    filtered_results.append(r)
                                    if rid:
                                        existing_ids.add(rid)
                                    continue

                                # 2) Si no hubo match en atributo: inferencia por embedding
                                emb_color = _infer_color_from_product_embedding(r.get('id'))
                                if emb_color and _matches_target_family(emb_color):
                                    filtered_results.append(r)
                                    if rid:
                                        existing_ids.add(rid)
                                    continue

                                # 3) Si no hubo match por embedding: fallback por nombre
                                #    Primero buscar términos explícitos de familia de color en el nombre.
                                name_txt = str(r.get('name') or '').strip().lower()
                                if name_txt and any(pref in name_txt for pref in preferred_set):
                                    filtered_results.append(r)
                                    if rid:
                                        existing_ids.add(rid)
                                    continue

                                #    Si no hay término explícito, NO inferir color semántico desde nombre completo.
                                #    Evita latencia alta y falsos positivos en textos largos (ej: nombres de producto).

                            _hang_trace(f"recovered_color semantic filtering done count={len(filtered_results)}")
                        except Exception:
                            filtered_results = [
                                r for r in formatted_results
                                if _resolve_product_color_norm(r) == recovered_color
                            ]

                        print(f"🎨 Filtrado color recuperado '{recovered_color}': {len(filtered_results)} resultados (exactos + cercanos)")

                        if filtered_results:
                            formatted_results = filtered_results
                            requested_attrs['color'] = recovered_color
                            all_available_values['color'] = [recovered_color]
                        else:
                            formatted_results = []
                            all_available_values['color'] = []
                    else:
                        formatted_results = []
                        print("🎨 Intención de color detectada sin mapeo ni recuperación CLIP válida: devolviendo 0 resultados")
                        _hang_trace("recovered_color flow -> no valid color, formatted_results=0")
                        color_key = next((k for k in requested_attrs.keys() if str(k).lower() == 'color'), None)
                        if color_key:
                            all_available_values[color_key] = []
                        elif detected_color_token:
                            all_available_values['color'] = []
                        filtered_results = []

                # Filtrar: mantener solo productos que cumplan AL MENOS 1 atributo solicitado
                filtered_results = [r for r in formatted_results if r.get("attributes_match_count", 0) > 0]
                _hang_trace(f"non-color attr filter count={len(filtered_results)}")
                # Para otros atributos, mantener fallback de no filtrar si quedaría vacío
                if filtered_results:
                    formatted_results = filtered_results

            # Reordenar: por cantidad de atributos cumplidos, luego stock, luego similitud
            # 🔄 PRIORIDAD: Productos no-fallback primero
            try:
                fallback_ids_set = fallback_product_ids  # Definido en el filtrado fuerte
            except NameError:
                fallback_ids_set = set()

            color_priority_score_fn, color_priority_target = _build_color_priority_score_fn(
                requested_attrs,
                detected_color_normalized,
                strict_exact_match=bool(detected_color_token)
            )
            for r in formatted_results:
                r['_color_priority_score'] = color_priority_score_fn(r)
            _hang_trace(f"color priority scoring done count={len(formatted_results)} target={color_priority_target}")
            if color_priority_enabled and color_priority_target:
                print(f"🎨 Color priority textual activo: target='{color_priority_target}'")

            formatted_results.sort(
                key=lambda r: (
                    0 if r.get("id") in fallback_ids_set else 1,  # No-fallback=1 (primero), Fallback=0 (después)
                    r.get("attributes_match_count", 0),
                    r.get("_color_priority_score", 0.0),
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )
            _hang_trace(f"final sort done count={len(formatted_results)}")
        else:
            # Si no hubo atributos solicitados, priorizar stock disponible y luego similitud
            all_available_values = {}
            color_priority_score_fn, color_priority_target = _build_color_priority_score_fn(
                {},
                detected_color_normalized,
                strict_exact_match=bool(detected_color_token)
            )
            for r in formatted_results:
                r['_color_priority_score'] = color_priority_score_fn(r)
            _hang_trace(f"else branch color priority scoring done count={len(formatted_results)} target={color_priority_target}")
            if color_priority_enabled and color_priority_target:
                print(f"🎨 Color priority textual activo: target='{color_priority_target}'")
            formatted_results.sort(
                key=lambda r: (
                    r.get("_color_priority_score", 0.0),
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )
            _hang_trace(f"else branch final sort done count={len(formatted_results)}")

        # Score dinamico por atributos solicitados (ej: color, manga, material, etc.)
        attr_priority_score_fn, attr_priority_weights = _build_attribute_priority_score_fn(
            requested_attrs,
            requested_attrs_confidence
        )
        for r in formatted_results:
            r['_attribute_priority_score'] = attr_priority_score_fn(r)

        if attr_priority_weights:
            print(f"[TEXT_SEARCH] Attribute priority activo: attrs={list(attr_priority_weights.keys())}")

        # Ranking final compuesto: prioriza fuerte atributos explicitos y color
        # sin hardcodear claves de negocio por cliente.
        try:
            has_attr_intent = bool(attr_priority_weights)
            has_color_intent = bool(detected_color_normalized)

            similarity_weight = 0.35 if has_attr_intent else 0.80
            attr_weight = 0.45 if has_attr_intent else 0.00
            color_weight = 0.20 if has_color_intent else 0.00
            total_weight = similarity_weight + attr_weight + color_weight
            if total_weight <= 0:
                total_weight = 1.0

            for r in formatted_results:
                sim_val = float(r.get("similarity", 0.0) or 0.0)
                attr_val = float(r.get("_attribute_priority_score", 0.0) or 0.0)
                color_val = float(r.get("_color_priority_score", 0.0) or 0.0)
                r['_final_rank_score'] = (
                    (similarity_weight * sim_val) +
                    (attr_weight * attr_val) +
                    (color_weight * color_val)
                ) / total_weight

            formatted_results.sort(
                key=lambda r: (
                    r.get("_final_rank_score", 0.0),
                    r.get("attributes_match_count", 0),
                    r.get("_color_priority_score", 0.0),
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )
            formatted_results = formatted_results[:limit]
            print(
                f"[TEXT_SEARCH] Ranking compuesto activo: "
                f"sim_w={similarity_weight:.2f}, attr_w={attr_weight:.2f}, color_w={color_weight:.2f}. "
                f"Devolviendo {len(formatted_results)} resultados (top {limit})"
            )
        except Exception as e_new_rank:
            print(f"⚠️ Error aplicando ranking final compuesto: {e_new_rank}")

        # Respuesta final
        elapsed = time.time() - start_time

        # MARCADOR TEMPRANO: Confirmar que el código llega aquí
        print(f"\n✅✅✅ BÚSQUEDA COMPLETADA - Punto A (ANTES de agrupación) ✅✅✅")
        print(f"   elapsed={elapsed:.3f}s")
        print(f"   formatted_results count: {len(formatted_results)}")
        print(f"   detection_metadata: {bool(detection_metadata)}")

        print(f"✅ Búsqueda completada: {len(formatted_results)} resultados en {elapsed:.3f}s")
        log_verbose(LogCategory.NLP, "="*60 + "\n")

        # 🔍 CONSTRUIR FEEDBACK DESCRIPTIVO (concepto del método deprecado)
        user_feedback = _build_user_feedback(
            query_text=query_text,
            formatted_results=formatted_results,
            detected_category_info=detection_metadata,  # Usar metadata de stage1
            client_id=client.id,
            attrs_requested=requested_attrs,
            contradictions=attr_info.get('contradictions', []),
            not_configured=[],  # 🆕 NO mostrar error sobre atributos no configurados (ya fueron excluidos del filtrado)
            all_available_values=all_available_values,  # Valores disponibles para los atributos filtrados
            detected_color_token=detected_color_token,  # Token original detectado como color
            detected_color_normalized=detected_color_normalized  # Color normalizado por LLM
        )

        if no_explicit_category:
            shown_categories = []
            for result in formatted_results:
                cat_name = result.get('category')
                if cat_name and cat_name not in shown_categories:
                    shown_categories.append(cat_name)

            if shown_categories:
                if len(shown_categories) == 1:
                    shown_text = shown_categories[0]
                elif len(shown_categories) == 2:
                    shown_text = f"{shown_categories[0]} y {shown_categories[1]}"
                else:
                    shown_text = f"{', '.join(shown_categories[:-1])} y {shown_categories[-1]}"

                user_feedback['message'] = (
                    "No detectamos una categoría exacta en tu descripción. "
                    f"Te mostramos resultados aproximados en: {shown_text}. "
                    "Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda."
                )
                user_feedback['has_results'] = True
                user_feedback['categories_shown'] = shown_categories
            else:
                user_feedback['message'] = (
                    "No detectamos una categoría exacta en tu descripción y no encontramos coincidencias aproximadas. "
                    "Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda."
                )
                user_feedback['has_results'] = False

            user_feedback['categories_available'] = available_names_for_guidance

        # Cargar atributos configurados para mapear etiquetas en el frontend
        # - exposed_attribute_keys: solo los marcados como visibles (comportamiento original)
        # - exposed_attribute_labels: mapa key->etiqueta para TODOS los atributos configurados (no depende de visible)
        exposed_attribute_keys = []
        exposed_attribute_labels = {}
        try:
            from app.models.product_attribute_config import ProductAttributeConfig
            configs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            for cfg in configs:
                key_l = (cfg.key or '').strip().lower()
                if not key_l:
                    continue
                # Mantener lista de visibles
                if cfg.expose_in_search:
                    exposed_attribute_keys.append(key_l)
                # Mapa de etiquetas para TODOS los atributos
                exposed_attribute_labels[key_l] = (cfg.label or cfg.key or key_l)
        except Exception:
            pass

        # Fallback: si el usuario pidió atributos no configurados, generar etiqueta legible
        # a partir de la clave (p. ej., 'con_bolsillo' -> 'Bolsillo') para evitar mostrar
        # nombres internos en la UI.
        try:
            requested_attrs = attr_info.get('attributes', {}) if isinstance(attr_info, dict) else {}
            def _beautify_label(k: str) -> str:
                base = str(k or '').strip().lower()
                if base.startswith('con_'):
                    base = base[4:]
                elif base.startswith('sin_'):
                    base = base[4:]
                base = base.replace('_', ' ').strip()
                return base.capitalize() if base else (k or '').capitalize()

            for k in requested_attrs.keys():
                kl = str(k).strip().lower()
                if kl and kl not in exposed_attribute_labels:
                    exposed_attribute_labels[kl] = _beautify_label(kl)
        except Exception:
            pass

        # ⭐ AGRUPACIÓN POR CATEGORÍAS HERMANAS CON TOP-UP
        # Estrategia: si múltiples categorías, devolver hasta 3 (MIN_CATEGORY_RESULTS) por categoría
        # Si una categoría queda con < 3, completar desde candidatos originales

        results_by_category = {}
        group_by_category = False
        MIN_CATEGORY_RESULTS = per_category_limit  # límite configurable por categoría

        # LOG CRÍTICO: Diagnosticar por qué no se agrupa
        import sys
        sys.stderr.flush()
        sys.stdout.flush()

        print(f"\n🎯🎯🎯 AGRUPACIÓN - DIAGNÓSTICO CRÍTICO 🎯🎯🎯")
        print(f"   detection_metadata exists: {bool(detection_metadata)}")
        print(f"   detection_metadata type: {type(detection_metadata)}")
        if detection_metadata:
            print(f"   detection_metadata keys: {detection_metadata.keys() if isinstance(detection_metadata, dict) else 'N/A'}")
            matched_cats = detection_metadata.get('matched_categories', [])
            print(f"   matched_categories count: {len(matched_cats)}")
            print(f"   matched_categories: {matched_cats}")
        print(f"   formatted_results count: {len(formatted_results)}")
        print(f"   formatted_results sample: {formatted_results[:2] if formatted_results else 'EMPTY'}")

        if detection_metadata and len(detection_metadata.get('matched_categories', [])) > 1:
            group_by_category = True
            log_error(f"✅ AGRUPACIÓN ACTIVADA: {len(detection_metadata.get('matched_categories', []))} categorías")

            # 1️⃣ Agrupar resultados filtrados por categoría
            for result in formatted_results:
                cat_name = result.get('category', 'Sin categoría')
                if cat_name not in results_by_category:
                    results_by_category[cat_name] = []
                results_by_category[cat_name].append(result)

            # 2️⃣ Recortar a MIN_CATEGORY_RESULTS (3) por categoría (tomar los mejores)
            for cat_name in results_by_category.keys():
                results_by_category[cat_name] = results_by_category[cat_name][:MIN_CATEGORY_RESULTS]

            # 3️⃣ TOP-UP: Completar categorías con < MIN_CATEGORY_RESULTS desde candidatos sin filtrar
            try:
                log_verbose(LogCategory.SEARCH, f"\n🔄 TOP-UP: Iniciando completado de categorías hasta {MIN_CATEGORY_RESULTS}")
                log_verbose(LogCategory.SEARCH, f"   Categorías actuales en results_by_category: {list(results_by_category.keys())}")
                log_verbose(LogCategory.SEARCH, f"   Cantidad por categoría: {[(k, len(v)) for k, v in results_by_category.items()]}")

                # IMPORTANTE: Obtener TODOS los productos de las categorías detectadas
                # (no solo los que pasaron filtrado), para rellenar hasta 3 por categoría
                all_matched_cat_ids = []
                if detection_metadata and detection_metadata.get('matched_categories'):
                    log_verbose(LogCategory.SEARCH, f"   Categorías detectadas en metadata: {detection_metadata.get('matched_categories')}")
                    for matched_cat in detection_metadata.get('matched_categories'):
                        # Buscar categoría - matched_cat son objetos dict con 'name', 'id', etc
                        if isinstance(matched_cat, dict):
                            cat_id = matched_cat.get('id')
                            cat_name = matched_cat.get('name')
                            if cat_id:
                                all_matched_cat_ids.append(cat_id)
                                log_verbose(LogCategory.SEARCH, f"      ✅ Categoría '{cat_name}' (ID: {cat_id}) agregada")
                        else:
                            # Si es string, buscar por nombre
                            cat = Category.query.filter_by(
                                client_id=client.id,
                                name=matched_cat
                            ).first()
                            if cat:
                                all_matched_cat_ids.append(cat.id)
                                log_verbose(LogCategory.SEARCH, f"      ✅ Categoría '{cat.name}' (ID: {cat.id}) agregada")
                            else:
                                log_verbose(LogCategory.SEARCH, f"      ⚠️ No se encontró categoría '{matched_cat}' en BD")

                # Mapa de TODOS los productos disponibles en las categorías detectadas
                candidates_by_cat = {}
                if all_matched_cat_ids:
                    all_available = Product.query.filter(
                        Product.client_id == client.id,
                        Product.category_id.in_(all_matched_cat_ids),
                        Product.is_active == True
                    ).all()

                    log_verbose(LogCategory.SEARCH, f"   Total productos disponibles en categorías detectadas: {len(all_available)}")

                    for prod in all_available:
                        cat = prod.category.name if prod.category else 'Sin categoría'
                        if cat not in candidates_by_cat:
                            candidates_by_cat[cat] = []
                        candidates_by_cat[cat].append(prod)

                    log_verbose(LogCategory.SEARCH, f"   Productos por categoría disponibles: {[(k, len(v)) for k, v in candidates_by_cat.items()]}")

                # Para cada categoría detectada, si tiene < MIN_CATEGORY_RESULTS, rellenar
                for cat_name, items in results_by_category.items():
                    initial_count = len(items)
                    if len(items) < MIN_CATEGORY_RESULTS and cat_name in candidates_by_cat:
                        existing_ids = {r.get('id') for r in items}
                        available = [c for c in candidates_by_cat[cat_name] if c.id not in existing_ids]

                        needed = MIN_CATEGORY_RESULTS - len(items)
                        log_verbose(LogCategory.SEARCH, f"   📦 {cat_name}: tiene {initial_count}, necesita {needed} más")
                        log_verbose(LogCategory.SEARCH, f"      Disponibles para agregar: {len(available)}")

                        # Agregar mejores candidatos hasta llegar a MIN_CATEGORY_RESULTS
                        for cand in available[:needed]:
                            pimg = cand.primary_image if hasattr(cand, 'primary_image') else (
                                Image.query.filter_by(product_id=cand.id, is_primary=True).first() or
                                Image.query.filter_by(product_id=cand.id).first()
                            )

                            # Priorizar external_url (Tiendanube) sobre url_producto (atributo)
                            cand_url = None
                            if hasattr(cand, 'external_url') and cand.external_url:
                                cand_url = cand.external_url
                            elif cand.attributes and cand.attributes.get('url_producto'):
                                raw = cand.attributes.get('url_producto')
                                if isinstance(raw, dict):
                                    cand_url = raw.get('value') or raw.get('url') or None
                                else:
                                    cand_url = raw

                            results_by_category[cat_name].append({
                                'id': cand.id,
                                'name': cand.name,
                                'price': float(cand.price) if cand.price else None,
                                'category': cat_name,
                                'stock': cand.stock,
                                'similarity': 0.0,
                                'final_score': 0.0,
                                'image': pimg.display_url if pimg else '/static/images/placeholder.svg',
                                'image_url': pimg.display_url if pimg else '/static/images/placeholder.svg',
                                'sku': cand.sku,
                                'attributes': cand.attributes or {},
                                'attributes_matched': {},
                                'attributes_match_count': 0,
                                'attributes_match_ratio': 0.0,
                                'product_url': cand_url  # URL para Tiendanube (prioriza external_url)
                            })

                        final_count = len(results_by_category[cat_name])
                        log_verbose(LogCategory.SEARCH, f"      ✅ {cat_name}: completada de {initial_count} a {final_count} productos")
                    elif len(items) < MIN_CATEGORY_RESULTS:
                        log_verbose(LogCategory.SEARCH, f"      ⚠️ {cat_name}: tiene {len(items)} pero no hay candidatos disponibles para rellenar")
                    else:
                        log_verbose(LogCategory.SEARCH, f"      ✓ {cat_name}: ya tiene {len(items)} productos (suficiente)")

            except Exception as e:
                import traceback
                log_verbose(LogCategory.SEARCH, f"⚠️ Top-up de categorías falló: {e}")
                log_verbose(LogCategory.SEARCH, f"   Traceback: {traceback.format_exc()}")

        # Construir respuesta
        response_data = {
            "success": True,
            "query": query_text,
            "expanded_terms": expanded_terms_cache,
            "stage1_candidates": len(candidates),
            "total_results": 0,  # Se actualiza abajo
            "processing_time": round(elapsed, 3),
            "search_module": "custom" if (client_slug and has_custom_module(client_slug)) else "generic",
            "user_feedback": user_feedback,
            "group_by_category": group_by_category,
            "categories_searched": user_feedback.get('categories_shown') or available_names_for_guidance,
            "exposed_attribute_keys": exposed_attribute_keys,
            "exposed_attribute_labels": exposed_attribute_labels
        }

        if group_by_category:
            response_data["results_by_category"] = results_by_category
            response_data["total_results"] = sum(len(v) for v in results_by_category.values())
            response_data["results"] = []
        else:
            response_data["results"] = formatted_results[:limit]
            response_data["total_results"] = len(response_data["results"])

        # 📊 ANALYTICS: Registrar búsqueda (async)
        try:
            print(f"🔍 ANALYTICS: Iniciando registro de búsqueda para client={client.id}", flush=True)
            # Extraer categorías
            cats_detected = []
            if detection_metadata:
                raw_matched_categories = detection_metadata.get('matched_categories', [])
                for cat_item in raw_matched_categories:
                    cat_name = None
                    if isinstance(cat_item, dict):
                        cat_name = cat_item.get('name') or cat_item.get('slug')
                    elif isinstance(cat_item, str):
                        cat_name = cat_item
                    else:
                        cat_name = getattr(cat_item, 'name', None) or getattr(cat_item, 'slug', None)

                    if cat_name:
                        cats_detected.append(str(cat_name))
            cats_matched = list(results_by_category.keys()) if group_by_category and results_by_category else (
                [cats_detected[0]] if cats_detected and formatted_results else []
            )
            cats_missing = [c for c in cats_detected if c not in cats_matched]

            # Extraer términos (modificadores y atributos)
            terms_extracted = []
            if 'attributes' in attr_info and isinstance(attr_info['attributes'], dict):
                for key, val in attr_info['attributes'].items():
                    if isinstance(val, list):
                        terms_extracted.extend([str(v).lower() for v in val])
                    else:
                        terms_extracted.append(str(val).lower())

            # Términos matcheados: atributos que aparecen en los resultados
            terms_matched = []
            terms_unmatched = list(terms_extracted)  # Inicialmente todos no matcheados
            if formatted_results:
                for result in formatted_results[:10]:  # Analizar top 10 para términos
                    result_attrs = result.get('attributes', {})
                    for term in list(terms_unmatched):
                        # Verificar si el término aparece en algún valor de atributo
                        for attr_val in result_attrs.values():
                            attr_str = str(attr_val).lower() if attr_val else ''
                            if term in attr_str:
                                if term not in terms_matched:
                                    terms_matched.append(term)
                                if term in terms_unmatched:
                                    terms_unmatched.remove(term)
                                break

            print(f"🔍 ANALYTICS: Llamando a SearchLog.log_search()", flush=True)
            SearchLog.log_search(
                client_id=client.id,
                search_type='text',
                query_text=query_text,
                image_url=None,
                categories_detected=cats_detected,
                categories_matched=cats_matched,
                categories_missing=cats_missing,
                terms_extracted=terms_extracted if terms_extracted else None,
                terms_matched=terms_matched if terms_matched else None,
                terms_unmatched=terms_unmatched if terms_unmatched else None,
                results_count=len(formatted_results),
                had_results=bool(formatted_results),
                response_time_ms=int(elapsed * 1000)
            )
            print(f"✅ ANALYTICS: SearchLog.log_search() completado", flush=True)
        except Exception as log_err:
            import traceback
            print(f"❌ ANALYTICS ERROR: {log_err}", flush=True)
            print(f"   Traceback: {traceback.format_exc()}", flush=True)
            print(f"❌ ERROR logging analytics: {log_err}")
            print(f"   Traceback: {traceback.format_exc()}")

        response = jsonify(response_data)

        # Agregar headers CORS explícitamente
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'

        return response

    except Exception as e:
        import traceback
        traceback.print_exc()

        response = jsonify({
            "success": False,
            "error": "internal_error",
            "message": str(e)
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500


_STRICT_COLOR_CONFIG_CACHE_V3 = {}
_STRICT_COLOR_PROMPT_CACHE_V3 = {}
_STRICT_COLOR_NORM_CACHE_V3 = {}


def _normalize_color_token_v3(value):
    import unicodedata as _ud

    txt = str(value or '').strip().lower()
    return ''.join(ch for ch in _ud.normalize('NFD', txt) if _ud.category(ch) != 'Mn')


def _tokenize_color_text_v3(value):
    txt = _normalize_color_token_v3(value)
    parts = []
    for chunk in txt.replace('/', ' ').replace(',', ' ').replace('-', ' ').split():
        token = chunk.strip(".,;:!?()[]{}\"'")
        if token:
            parts.append(token)
    return parts


def _flatten_attribute_values_v3(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, dict):
        values = []
        for val in raw_value.values():
            values.extend(_flatten_attribute_values_v3(val))
        return values
    if isinstance(raw_value, list):
        values = []
        for val in raw_value:
            values.extend(_flatten_attribute_values_v3(val))
        return values
    return [str(raw_value)]


def _attribute_value_matches_v3(product_value, requested_value):
    product_values = {
        _normalize_color_token_v3(v)
        for v in _flatten_attribute_values_v3(product_value)
        if str(v).strip()
    }
    requested_values = {
        _normalize_color_token_v3(v)
        for v in _flatten_attribute_values_v3(requested_value)
        if str(v).strip()
    }
    if not product_values or not requested_values:
        return False
    return bool(product_values & requested_values)


def _get_color_family_keys_v3(target_color):
    target_norm = _normalize_color_token_v3(target_color)
    return [target_norm] if target_norm else []


def _normalize_color_semantic_v3(value, client_id=None):
    cache_key = f"{str(client_id)}:{_normalize_color_token_v3(value)}"
    if cache_key in _STRICT_COLOR_NORM_CACHE_V3:
        return _STRICT_COLOR_NORM_CACHE_V3[cache_key]

    resolved = _normalize_color_token_v3(value)
    try:
        from app.utils.colors import normalize_color

        llm_color = normalize_color(str(value or ''), client_id=client_id)
        if llm_color:
            resolved = _normalize_color_token_v3(llm_color)
    except Exception:
        pass

    _STRICT_COLOR_NORM_CACHE_V3[cache_key] = resolved
    return resolved


def _extract_option_terms_v3(raw_options):
    terms = []
    decoded = raw_options

    if isinstance(raw_options, str) and raw_options.strip():
        try:
            decoded = _json_nlp.loads(raw_options)
        except Exception:
            try:
                import ast
                decoded = ast.literal_eval(raw_options)
            except Exception:
                decoded = raw_options

    if isinstance(decoded, dict):
        if isinstance(decoded.get('values'), list):
            decoded = decoded.get('values')
        else:
            decoded = list(decoded.keys())

    if isinstance(decoded, list):
        for item in decoded:
            if isinstance(item, dict):
                candidate = item.get('value') or item.get('label') or item.get('name')
                if candidate is not None:
                    terms.append(str(candidate))
            elif item is not None:
                terms.append(str(item))
    elif decoded is not None:
        terms.append(str(decoded))

    return terms


def _get_client_color_terms_v3(client_id):
    cache_key = str(client_id)
    if cache_key in _STRICT_COLOR_CONFIG_CACHE_V3:
        return list(_STRICT_COLOR_CONFIG_CACHE_V3[cache_key])

    terms = set()

    try:
        from app.models.product_attribute_config import ProductAttributeConfig

        configs = ProductAttributeConfig.query.filter_by(client_id=client_id).all()
        for cfg in configs:
            cfg_key = _normalize_color_token_v3(getattr(cfg, 'key', ''))
            if 'color' not in cfg_key:
                continue

            for option_term in _extract_option_terms_v3(getattr(cfg, 'options', None)):
                norm = _normalize_color_token_v3(option_term)
                if norm:
                    terms.add(norm)
                for token in _tokenize_color_text_v3(option_term):
                    terms.add(token)
    except Exception:
        pass

    try:
        from app.utils.semantic_colors import get_system_color_adjectives, _load_system_colors

        for token in get_system_color_adjectives():
            norm = _normalize_color_token_v3(token)
            if norm:
                terms.add(norm)

        data_sc = _load_system_colors()
        entries = data_sc.get('colors', []) if isinstance(data_sc, dict) else []
        for item in entries:
            token = _normalize_color_token_v3(item.get('token', ''))
            if token:
                terms.add(token)
            for alias in item.get('aliases', []) or []:
                norm_alias = _normalize_color_token_v3(alias)
                if norm_alias:
                    terms.add(norm_alias)
            for preferred in item.get('preferred_matches', []) or []:
                norm_pref = _normalize_color_token_v3(preferred)
                if norm_pref:
                    terms.add(norm_pref)
    except Exception:
        pass

    _STRICT_COLOR_CONFIG_CACHE_V3[cache_key] = sorted(terms)
    return list(_STRICT_COLOR_CONFIG_CACHE_V3[cache_key])


def _build_color_terms_v3(client_id, target_color=None, related_colors=None):
    terms = set(_get_client_color_terms_v3(client_id))

    def _extend_from_value(raw_value):
        norm = _normalize_color_token_v3(raw_value)
        if norm:
            terms.add(norm)
        for token in _tokenize_color_text_v3(raw_value):
            terms.add(token)

    if target_color:
        _extend_from_value(target_color)
    for rel in (related_colors or []):
        _extend_from_value(rel)

    return sorted(t for t in terms if t and len(t) >= 3)


def _ensure_color_prompt_matrix_v3(color_terms):
    key = tuple(sorted(set(color_terms or [])))
    if key in _STRICT_COLOR_PROMPT_CACHE_V3:
        return _STRICT_COLOR_PROMPT_CACHE_V3[key]

    if not key:
        return [], np.array([])

    clip_model, clip_processor = get_clip_model()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    prompts = []
    prompt_terms = []
    for term in key:
        prompts.append(f"a photo of a {term} garment")
        prompt_terms.append(term)
        prompts.append(f"una prenda color {term}")
        prompt_terms.append(term)

    with torch.no_grad():
        text_inputs = clip_processor(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(device)
        text_embeddings = clip_model.get_text_features(**text_inputs)
        text_embeddings = text_embeddings / text_embeddings.norm(dim=-1, keepdim=True)

    matrix = text_embeddings.cpu().numpy().astype(np.float32)
    _STRICT_COLOR_PROMPT_CACHE_V3[key] = (prompt_terms, matrix)
    return _STRICT_COLOR_PROMPT_CACHE_V3[key]


def _score_image_color_similarity_v3(image_obj, target_color, related_colors=None, client_id=None, color_terms=None):
    if image_obj is None or not getattr(image_obj, 'clip_embedding', None):
        return 0.0

    try:
        dynamic_terms = color_terms or _build_color_terms_v3(client_id, target_color, related_colors)
        prompt_terms, matrix = _ensure_color_prompt_matrix_v3(dynamic_terms)
    except Exception:
        return 0.0

    if not prompt_terms or getattr(matrix, 'size', 0) == 0:
        return 0.0

    try:
        raw_embedding = image_obj.clip_embedding
        if isinstance(raw_embedding, str):
            image_vec = np.asarray(_json_nlp.loads(raw_embedding), dtype=np.float32)
        elif isinstance(raw_embedding, list):
            image_vec = np.asarray(raw_embedding, dtype=np.float32)
        else:
            return 0.0
    except Exception:
        return 0.0

    if image_vec.ndim != 1:
        image_vec = image_vec.reshape(-1)
    if matrix.shape[1] != image_vec.shape[0]:
        return 0.0

    image_norm = np.linalg.norm(image_vec)
    if image_norm == 0:
        return 0.0
    image_vec = image_vec / image_norm

    target_norm = _normalize_color_semantic_v3(target_color, client_id=client_id)
    candidate_norms = {target_norm}
    for token in _tokenize_color_text_v3(target_color):
        candidate_norms.add(_normalize_color_semantic_v3(token, client_id=client_id))
    if related_colors:
        for item in related_colors:
            candidate_norms.add(_normalize_color_semantic_v3(item, client_id=client_id))
            for token in _tokenize_color_text_v3(item):
                candidate_norms.add(_normalize_color_semantic_v3(token, client_id=client_id))

    candidate_indexes = []
    for idx, term in enumerate(prompt_terms):
        term_norm = _normalize_color_semantic_v3(term, client_id=client_id)
        if term_norm in candidate_norms:
            candidate_indexes.append(idx)

    if not candidate_indexes:
        return 0.0

    sims = np.dot(matrix, image_vec)
    best = max(float(sims[idx]) for idx in candidate_indexes)
    return max(0.0, min(0.99, best))


def _product_matches_color_lexically_v3(attributes, target_color, related_colors=None, client_id=None, color_terms=None):
    if not isinstance(attributes, dict):
        return False

    target_norms = {_normalize_color_semantic_v3(target_color, client_id=client_id)}
    for token in _tokenize_color_text_v3(target_color):
        target_norms.add(_normalize_color_semantic_v3(token, client_id=client_id))

    if related_colors:
        for item in related_colors:
            target_norms.add(_normalize_color_semantic_v3(item, client_id=client_id))
            for token in _tokenize_color_text_v3(item):
                target_norms.add(_normalize_color_semantic_v3(token, client_id=client_id))

    candidate_tokens = set()
    for term in (color_terms or []):
        term_norm = _normalize_color_semantic_v3(term, client_id=client_id)
        if term_norm in target_norms:
            candidate_tokens.add(_normalize_color_token_v3(term))
            for tok in _tokenize_color_text_v3(term):
                candidate_tokens.add(tok)

    if not candidate_tokens:
        candidate_tokens.update(_tokenize_color_text_v3(target_color))
        candidate_tokens.add(_normalize_color_token_v3(target_color))
        for item in (related_colors or []):
            candidate_tokens.update(_tokenize_color_text_v3(item))
            candidate_tokens.add(_normalize_color_token_v3(item))

    for key, raw_value in attributes.items():
        key_norm = _normalize_color_token_v3(key)
        if 'color' not in key_norm:
            continue
        raw_tokens = []
        for value in _flatten_attribute_values_v3(raw_value):
            raw_tokens.extend(_tokenize_color_text_v3(value))
        for token in raw_tokens:
            if token in candidate_tokens:
                return True
            token_norm = _normalize_color_semantic_v3(token, client_id=client_id)
            if token_norm in target_norms:
                return True

    return False


def _extract_text_color_signals_v3(text, client_id=None, color_terms=None):
    raw_text = str(text or '').strip()
    if not raw_text:
        return set()

    known_terms = {
        _normalize_color_token_v3(term)
        for term in (color_terms or [])
        if str(term).strip()
    }
    if not known_terms and client_id:
        known_terms = {
            _normalize_color_token_v3(term)
            for term in _get_client_color_terms_v3(client_id)
            if str(term).strip()
        }

    if not known_terms:
        return set()

    tokens = _tokenize_color_text_v3(raw_text)
    if not tokens:
        return set()

    # Detecta colores de una y dos palabras (ej: "azul marino").
    chunks = list(tokens)
    for idx in range(len(tokens) - 1):
        chunks.append(f"{tokens[idx]} {tokens[idx + 1]}")

    detected = set()
    for chunk in chunks:
        chunk_norm = _normalize_color_token_v3(chunk)
        if chunk_norm not in known_terms:
            continue
        normalized = _normalize_color_semantic_v3(chunk_norm, client_id=client_id)
        if normalized:
            detected.add(normalized)

    return detected


def _detect_color_intent_v3(query_text, requested_attrs, client_id):
    from app.utils.colors import normalize_color

    detected_color_token = None
    detected_color_normalized = None
    detected_color_intent = False
    semantic_related_colors = []

    preferred_map = {}
    excluded_tokens = set()
    system_color_adjectives = set()
    client_color_terms = set()

    try:
        from app.utils.semantic_colors import get_system_color_adjectives, _load_system_colors

        system_color_adjectives = {
            _normalize_color_token_v3(c)
            for c in get_system_color_adjectives()
            if str(c).strip()
        }
        data_sc = _load_system_colors()
        entries = data_sc.get('colors', []) if isinstance(data_sc, dict) else []
        for item in entries:
            token = _normalize_color_token_v3(item.get('token', ''))
            if not token:
                continue
            preferred = [
                _normalize_color_token_v3(v)
                for v in (item.get('preferred_matches') or [])
                if str(v).strip()
            ]
            if preferred:
                preferred_map[token] = preferred
        excluded_cfg = data_sc.get('excluded_tokens', {}) if isinstance(data_sc, dict) else {}
        if isinstance(excluded_cfg, dict):
            for cfg_key, cfg_values in excluded_cfg.items():
                if cfg_key in ('description', 'min_token_length', 'require_adj_pos'):
                    continue
                if isinstance(cfg_values, list):
                    for value in cfg_values:
                        token = _normalize_color_token_v3(value)
                        if token:
                            excluded_tokens.add(token)
    except Exception:
        system_color_adjectives = set()

    raw_color_values = []
    if isinstance(requested_attrs, dict):
        for key, value in requested_attrs.items():
            if _normalize_color_token_v3(key) == 'color':
                raw_color_values.extend(_flatten_attribute_values_v3(value))

    if raw_color_values:
        detected_color_intent = True
        detected_color_token = _normalize_color_token_v3(raw_color_values[0])
        normalized = normalize_color(detected_color_token, client_id=client_id)
        if normalized:
            detected_color_normalized = _normalize_color_token_v3(normalized)
        elif detected_color_token in preferred_map:
            semantic_related_colors = preferred_map[detected_color_token]
            detected_color_normalized = semantic_related_colors[0]
        else:
            detected_color_normalized = detected_color_token

    # Si el color ya viene explícitamente del extractor/atributo, no lo pisamos
    # con tokens sueltos del texto libre (ej: "estoy" -> beige).
    if detected_color_normalized:
        return {
            'detected_color_token': detected_color_token,
            'detected_color_normalized': detected_color_normalized,
            'detected_color_intent': detected_color_intent,
            'semantic_related_colors': semantic_related_colors,
        }

    try:
        client_color_terms = {
            _normalize_color_token_v3(t)
            for t in _get_client_color_terms_v3(client_id)
            if str(t).strip()
        }
    except Exception:
        client_color_terms = set()

    query_tokens = _tokenize_color_text_v3(query_text)
    for token in query_tokens:
        if token in excluded_tokens:
            continue

        # Evita normalizar cualquier token de la frase como color.
        # Solo procesamos tokens plausibles de color según vocabulario/config.
        if token not in preferred_map and token not in system_color_adjectives and token not in client_color_terms:
            continue

        if token in preferred_map:
            detected_color_intent = True
            detected_color_token = token
            semantic_related_colors = preferred_map[token]
            detected_color_normalized = semantic_related_colors[0]
            break

        normalized = normalize_color(token, client_id=client_id)
        if normalized:
            detected_color_intent = True
            detected_color_token = token
            detected_color_normalized = _normalize_color_token_v3(normalized)
            break

        if token in system_color_adjectives:
            detected_color_intent = True
            detected_color_token = token
            if not detected_color_normalized:
                detected_color_normalized = token

    return {
        'detected_color_token': detected_color_token,
        'detected_color_normalized': detected_color_normalized,
        'detected_color_intent': detected_color_intent,
        'semantic_related_colors': semantic_related_colors,
    }


def _json_response_with_cors_v3(payload, status_code=200):
    response = jsonify(payload)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.status_code = status_code
    return response


@bp.route("/search/text", methods=["POST", "OPTIONS"])
def text_search():
    if request.method == 'OPTIONS':
        return _json_response_with_cors_v3({'status': 'ok'})

    start_time = time.time()

    try:
        client, error = verify_api_key()
        if error:
            return _json_response_with_cors_v3({
                'success': False,
                'error': 'invalid_api_key',
                'message': error,
            }, 401)

        data = request.get_json(silent=True) or {}
        query_text = str(data.get('query', '')).strip()
        if not query_text:
            return _json_response_with_cors_v3({
                'success': False,
                'error': 'invalid_request',
                'message': 'query requerida',
            }, 400)

        default_max_results = system_config.get('search', 'max_results', 10)
        limit = min(int(data.get('limit', default_max_results)), default_max_results)
        if limit < 1:
            limit = 1
        per_category_limit = min(int(data.get('max_results_per_category', 5)), default_max_results)
        if per_category_limit < 1:
            per_category_limit = 1

        client_slug = getattr(client, 'slug', None)

        try:
            client_profile = SearchProfilesService.get_profile(str(client.id), client.industry)
        except Exception:
            client_profile = None

        extraction_result = _extract_key_terms_with_dependency_parsing(query_text, client_profile)
        cleaned_query = str(extraction_result.get('text') or '').strip()

        attr_info = extract_query_attributes(query_text, client.id) or {}
        requested_attrs = attr_info.get('attributes', {}) or {}
        not_configured_attrs = [str(v).strip().lower() for v in (attr_info.get('not_configured', []) or []) if str(v).strip()]
        if not_configured_attrs:
            requested_attrs = {
                key: value
                for key, value in requested_attrs.items()
                if _normalize_color_token_v3(key) not in not_configured_attrs
            }

        color_detection = _detect_color_intent_v3(query_text, requested_attrs, client.id)
        detected_color_token = color_detection.get('detected_color_token')
        detected_color_normalized = color_detection.get('detected_color_normalized')
        detected_color_intent = bool(color_detection.get('detected_color_intent'))
        semantic_related_colors = color_detection.get('semantic_related_colors') or []

        candidates, detection_metadata = stage1_broad_recall(
            query_text,
            client.id,
            client_slug,
            is_color_search=detected_color_intent,
        )
        expanded_terms_cache = expand_query_with_synonyms(query_text, client.id, client_slug)

        matched_categories = []
        if isinstance(detection_metadata, dict):
            matched_categories = detection_metadata.get('matched_categories') or []

        no_explicit_category = not detection_metadata or not matched_categories
        available_names_for_guidance = []
        if no_explicit_category:
            try:
                available_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
                available_names_for_guidance = [cat.name for cat in available_categories if getattr(cat, 'name', None)]
            except Exception:
                available_names_for_guidance = []

        if not candidates:
            if no_explicit_category:
                user_feedback = {
                    'message': 'No detectamos una categoría exacta en tu descripción. Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda.',
                    'has_results': False,
                    'categories_available': available_names_for_guidance,
                    'suggestion': "Ejemplo: 'chaqueta azul para cocina' o 'delantal azul'.",
                }
            else:
                user_feedback = {
                    'message': 'No se encontraron productos para la búsqueda solicitada.',
                    'has_results': False,
                }

            return _json_response_with_cors_v3({
                'success': True,
                'query': query_text,
                'expanded_terms': expanded_terms_cache,
                'stage1_candidates': 0,
                'total_results': 0,
                'processing_time': round(time.time() - start_time, 3),
                'search_module': 'custom' if (client_slug and has_custom_module(client_slug)) else 'generic',
                'user_feedback': user_feedback,
                'results': [],
                'results_by_category': {},
                'group_by_category': False,
                'categories_searched': available_names_for_guidance if no_explicit_category else [],
                'detection': {
                    'categorias_matched': matched_categories,
                    'tiene_match': bool(matched_categories),
                },
                'analysis': {
                    'atributos_encontrados': list(requested_attrs.keys()),
                    'modificadores_no_configurados': not_configured_attrs,
                },
            })

        clip_query_text = _build_clip_query_from_extraction(
            extraction_result,
            client.id,
            detected_color_token=detected_color_token,
            detected_color_normalized=detected_color_normalized,
        )
        if not clip_query_text:
            clip_query_text = cleaned_query or query_text

        rerank_limit = min(len(candidates), max(limit * 10, 50)) if detected_color_intent else limit
        scored_results = stage2_precise_rerank(clip_query_text, candidates, limit=rerank_limit)

        requested_attrs_for_match = {
            key: value for key, value in requested_attrs.items()
            if _normalize_color_token_v3(key) != 'color'
        }
        requested_count = len(requested_attrs_for_match)

        # Labels para que el widget renderice correctamente "Filtrando".
        attribute_labels = {}
        try:
            from app.models.product_attribute_config import ProductAttributeConfig

            cfgs = ProductAttributeConfig.query.filter_by(client_id=client.id).all()
            for cfg in cfgs:
                key_norm = _normalize_color_token_v3(getattr(cfg, 'key', ''))
                if key_norm:
                    attribute_labels[key_norm] = (getattr(cfg, 'label', None) or getattr(cfg, 'key', key_norm))
        except Exception:
            attribute_labels = {}

        def _scalar_for_analysis(raw_value):
            values = [v for v in _flatten_attribute_values_v3(raw_value) if str(v).strip()]
            return values[0] if values else None

        analysis_attrs = []
        for key, value in requested_attrs.items():
            key_norm = _normalize_color_token_v3(key)
            analysis_attrs.append({
                'atributo_key': key_norm,
                'atributo_label': attribute_labels.get(key_norm, key_norm),
                'valor_detectado': _scalar_for_analysis(value),
            })

        if detected_color_intent and detected_color_normalized and not any(
            _normalize_color_token_v3(item.get('atributo_key', '')) == 'color'
            for item in analysis_attrs
        ):
            analysis_attrs.append({
                'atributo_key': 'color',
                'atributo_label': attribute_labels.get('color', 'color'),
                'valor_detectado': detected_color_normalized,
            })

        # Umbral más permisivo: CLIP detecta azul a 0.25+ incluso sin atributo configurado
        strict_color_min_score = 0.25
        dynamic_color_terms = []
        target_color_norms = set()
        if detected_color_intent and detected_color_normalized:
            dynamic_color_terms = _build_color_terms_v3(
                client.id,
                detected_color_normalized,
                semantic_related_colors,
            )
            target_color_norms.add(
                _normalize_color_semantic_v3(detected_color_normalized, client_id=client.id)
            )
            for token in _tokenize_color_text_v3(detected_color_normalized):
                target_color_norms.add(_normalize_color_semantic_v3(token, client_id=client.id))
            for rel in semantic_related_colors:
                target_color_norms.add(_normalize_color_semantic_v3(rel, client_id=client.id))
                for token in _tokenize_color_text_v3(rel):
                    target_color_norms.add(_normalize_color_semantic_v3(token, client_id=client.id))
            target_color_norms = {v for v in target_color_norms if v}

        formatted_results = []
        for result in scored_results:
            product = result.get('product')
            if product is None:
                continue

            primary_image = result.get('image')
            if not primary_image:
                primary_image = Image.query.filter_by(product_id=product.id, is_primary=True).first()
            if not primary_image:
                primary_image = Image.query.filter_by(product_id=product.id).first()

            prod_attrs = product.attributes or {}
            matched = {}
            for key, value in requested_attrs_for_match.items():
                if key not in prod_attrs:
                    continue
                if _attribute_value_matches_v3(prod_attrs.get(key), value):
                    matched[key] = value

            matched_count = len(matched)
            match_ratio = float(matched_count / requested_count) if requested_count > 0 else 0.0

            color_visual_score = 0.0
            color_attr_lexical_match = False
            color_name_lexical_match = False
            color_match_priority = 0
            if detected_color_intent and detected_color_normalized:
                has_color_attr_value = any(
                    'color' in _normalize_color_token_v3(attr_key)
                    and any(str(v).strip() for v in _flatten_attribute_values_v3(attr_val))
                    for attr_key, attr_val in (prod_attrs or {}).items()
                )

                color_visual_score = _score_image_color_similarity_v3(
                    primary_image,
                    detected_color_normalized,
                    semantic_related_colors,
                    client_id=client.id,
                    color_terms=dynamic_color_terms,
                )
                color_attr_lexical_match = _product_matches_color_lexically_v3(
                    prod_attrs,
                    detected_color_normalized,
                    semantic_related_colors,
                    client_id=client.id,
                    color_terms=dynamic_color_terms,
                )
                name_color_signals = _extract_text_color_signals_v3(
                    getattr(product, 'name', ''),
                    client_id=client.id,
                    color_terms=dynamic_color_terms,
                )
                has_target_name_color = bool(name_color_signals & target_color_norms)
                color_name_lexical_match = has_target_name_color

                # Prioridad estricta pedida:
                # 1) atributo configurado, 2) embedding visual, 3) nombre (solo fallback).
                if has_color_attr_value:
                    if color_attr_lexical_match:
                        color_match_priority = 3
                    elif color_visual_score >= strict_color_min_score:
                        # Fallback: si atributo existe pero léxico falla, intentar visual
                        color_match_priority = 2
                    else:
                        continue
                elif color_visual_score >= strict_color_min_score:
                    color_match_priority = 2
                elif color_name_lexical_match:
                    color_match_priority = 1
                else:
                    continue

            final_product_url = None
            if hasattr(product, 'external_url') and product.external_url:
                final_product_url = product.external_url
            elif prod_attrs.get('url_producto'):
                raw_url = prod_attrs.get('url_producto')
                if isinstance(raw_url, dict):
                    final_product_url = raw_url.get('value') or raw_url.get('url') or None
                else:
                    final_product_url = raw_url

            similarity = float(result.get('similarity') or 0.0)
            color_priority_score = color_visual_score
            if color_match_priority == 3:
                color_priority_score = max(color_priority_score, 0.95)

            formatted_results.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price) if product.price is not None else None,
                'similarity': round(similarity, 3),
                'final_score': round(similarity, 3),
                'image': primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                'image_url': primary_image.display_url if primary_image else '/static/images/placeholder.svg',
                'category': product.category.name if product.category else None,
                'attributes': prod_attrs,
                'attributes_matched': matched,
                'attributes_match_count': matched_count,
                'attributes_match_ratio': round(match_ratio, 3),
                'sku': product.sku,
                'stock': product.stock,
                'product_url': final_product_url,
                '_color_priority_score': round(color_priority_score, 4),
                '_color_match_priority': int(color_match_priority),
            })

        # Detectar si habrá grouping ANTES de ordenar
        results_by_category = {}
        category_order = []
        for row in formatted_results:
            category_name = row.get('category') or 'Sin categoría'
            if category_name not in category_order:
                category_order.append(category_name)

        should_group_by_category = len(category_order) > 1

        # Solo reordenar por color si NO hay grouping (búsqueda de color singular).
        # Si hay múltiples categorías, mantener ranking de CLIP que ya es óptimo.
        if detected_color_intent and not should_group_by_category:
            formatted_results.sort(
                key=lambda row: (
                    int(row.get('_color_match_priority', 0)),
                    float(row.get('_color_priority_score', 0.0)),
                    float(row.get('attributes_match_ratio', 0.0)),
                    float(row.get('similarity', 0.0)),
                ),
                reverse=True,
            )
        elif not detected_color_intent:
            formatted_results.sort(
                key=lambda row: (
                    float(row.get('attributes_match_ratio', 0.0)),
                    float(row.get('similarity', 0.0)),
                ),
                reverse=True,
            )
        if should_group_by_category:
            for row in formatted_results:
                category_name = row.get('category') or 'Sin categoría'
                bucket = results_by_category.setdefault(category_name, [])
                if len(bucket) < per_category_limit:
                    bucket.append(row)

        group_by_category = bool(should_group_by_category and results_by_category)

        if group_by_category:
            limited_results = []
            for _, items in results_by_category.items():
                limited_results.extend(items)
        else:
            limited_results = formatted_results[:limit]

        for row in limited_results:
            row.pop('_color_priority_score', None)
            row.pop('_color_match_priority', None)

        detected_category_info = {
            'requested_term': extraction_result.get('category'),
            'matched_categories': [
                c.get('name') if isinstance(c, dict) else getattr(c, 'name', None)
                for c in matched_categories
            ]
        }

        feedback = _build_user_feedback(
            query_text=query_text,
            formatted_results=limited_results,
            detected_category_info=detected_category_info,
            client_id=client.id,
            attrs_requested=requested_attrs,
            contradictions=[],
            not_configured=not_configured_attrs,
            all_available_values={},
            detected_color_token=detected_color_token,
            detected_color_normalized=detected_color_normalized,
        )

        if no_explicit_category:
            shown_categories = []
            for result in limited_results:
                cat_name = result.get('category')
                if cat_name and cat_name not in shown_categories:
                    shown_categories.append(cat_name)

            if shown_categories:
                if len(shown_categories) == 1:
                    shown_text = shown_categories[0]
                elif len(shown_categories) == 2:
                    shown_text = f"{shown_categories[0]} y {shown_categories[1]}"
                else:
                    shown_text = f"{', '.join(shown_categories[:-1])} y {shown_categories[-1]}"

                feedback['message'] = (
                    "No detectamos una categoría exacta en tu descripción. "
                    f"Te mostramos resultados aproximados en: {shown_text}. "
                    "Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda."
                )
                feedback['has_results'] = True
                feedback['categories_shown'] = shown_categories
            else:
                feedback['message'] = (
                    "No detectamos una categoría exacta en tu descripción y no encontramos coincidencias aproximadas. "
                    "Si nos indicas el tipo de prenda o categoría, refinamos mejor la búsqueda."
                )
                feedback['has_results'] = False

            feedback['categories_available'] = available_names_for_guidance

        elapsed = time.time() - start_time
        response_data = {
            'success': True,
            'query': query_text,
            'expanded_terms': expanded_terms_cache,
            'stage1_candidates': len(candidates),
            'total_results': len(limited_results),
            'processing_time': round(elapsed, 3),
            'search_module': 'custom' if (client_slug and has_custom_module(client_slug)) else 'generic',
            'user_feedback': feedback,
            'results': limited_results,
            'results_by_category': results_by_category if group_by_category else {},
            'group_by_category': group_by_category,
            'categories_searched': feedback.get('categories_shown') or available_names_for_guidance,
            'detection': {
                'categorias_matched': matched_categories,
                'tiene_match': bool(matched_categories),
            },
            'analysis': {
                'atributos_encontrados': analysis_attrs,
                'modificadores_no_configurados': not_configured_attrs,
                'color_detectado': detected_color_normalized,
                'intencion_color': detected_color_intent,
            },
        }

        try:
            detected_categories = [
                c.get('name') if isinstance(c, dict) else getattr(c, 'name', None)
                for c in matched_categories
            ]
            detected_categories = [c for c in detected_categories if c]

            extracted_terms = [
                str(v).strip().lower()
                for v in (extraction_result.get('modifiers') or [])
                if str(v).strip()
            ]
            matched_terms = []
            unmatched_terms = list(extracted_terms)
            for row in limited_results:
                attrs = row.get('attributes') or {}
                attrs_values = ' '.join(
                    str(v).lower() for v in attrs.values() if v is not None
                )
                for term in list(unmatched_terms):
                    if term in attrs_values:
                        if term not in matched_terms:
                            matched_terms.append(term)
                        unmatched_terms.remove(term)

            SearchLog.log_search(
                client_id=client.id,
                search_type='text',
                query_text=query_text,
                image_url=None,
                categories_detected=detected_categories or None,
                categories_matched=detected_categories or None,
                categories_missing=None,
                terms_extracted=extracted_terms or None,
                terms_matched=matched_terms or None,
                terms_unmatched=unmatched_terms or None,
                results_count=len(limited_results),
                had_results=bool(limited_results),
                response_time_ms=int(elapsed * 1000),
            )
        except Exception as analytics_error:
            log_error(f"Error registrando analytics en text_search nuevo: {analytics_error}")

        return _json_response_with_cors_v3(response_data)

    except Exception as e:
        log_error(f"Error en text_search nuevo: {e}")
        return _json_response_with_cors_v3({
            'success': False,
            'error': 'internal_error',
            'message': str(e),
        }, 500)
