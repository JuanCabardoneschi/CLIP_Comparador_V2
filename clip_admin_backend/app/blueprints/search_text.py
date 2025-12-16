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
    fallback_added = []
    processed_lemmas = {e.lower() for e in elementos_extraidos}
    processed_lemmas.update(nivel2_discarded)  # Excluir términos nivel 2 del fallback

    for token in doc:
        if not token.is_alpha or token.is_stop or token.pos_ == 'VERB':
            continue
        if token.pos_ not in ('NOUN', 'PROPN') and token.text.lower() not in FASHION_TERMS:
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


def stage1_broad_recall(query_text: str, client_id: str, client_slug: str = None, top_n: int = 50):
    # STAGE 1: Broad Recall - PostgreSQL SIMILAR TO (sin docstring multiline para evitar errores)
    start_time = time.time()

    # 1️⃣ Expandir query con sinónimos (ahora usa proveedor de perfiles)
    expanded_tokens = expand_query_with_synonyms(query_text, client_id, client_slug)

    # 1.1 Detectar categorías para filtrar (usa proveedor de perfiles)
    categories = Category.query.filter_by(client_id=client_id).all()
    category_filter_ids = []
    detection_metadata = None

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
            log_verbose(LogCategory.SEARCH, f"[Perfil de Búsqueda] Filtro de categoría: {len(category_filter_ids)} categorías")
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
            # Fallback genérico
            original_tokens = _normalize_tokens_es(query_text)
            color_tokens = {"rojo", "verde", "azul", "negro", "blanco", "marron", "gris", "beige", "rosa", "amarillo", "violeta"}
            filtered_query_tokens = [t for t in original_tokens if t not in color_tokens]

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

    # Normalizar category_filter_ids para SQL
    if not category_filter_ids:
        category_filter_ids = []

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
        "  LOWER(p.name) SIMILAR TO :pattern "
        "  OR (p.attributes IS NOT NULL AND jsonb_typeof(p.attributes) = 'object' AND EXISTS ("
        "       SELECT 1 FROM jsonb_each_text(p.attributes) attr WHERE LOWER(attr.value) SIMILAR TO :pattern"
        "     )) "
        "  OR (LOWER(c.name) SIMILAR TO :pattern OR LOWER(c.name_en) SIMILAR TO :pattern OR LOWER(c.alternative_terms) SIMILAR TO :pattern) "
        ") "
        "LIMIT :limit"
    )
    sql = text(sql_query_stage1)

    product_ids = db.session.execute(sql, {
        "client_id": client_id,
        "pattern": pattern,
        "limit": top_n,
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


def stage2_precise_rerank(query_text: str, candidates: list, limit: int = 10):
    # STAGE 2: Precise Reranking - usa similitud CLIP text-to-text
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

    # 3️⃣ Calcular similitud con TEXTO de cada producto
    scored_candidates = []

    for product in candidates:
        # Construir descripción textual del producto
        product_parts = [product.name]

        # Agregar atributos relevantes
        if product.attributes:
            for key in ['color', 'tipo', 'material', 'talla']:
                if key in product.attributes and product.attributes[key]:
                    product_parts.append(str(product.attributes[key]))

        # Agregar categoría
        if product.category:
            product_parts.append(product.category.name)
            if product.category.name_en:
                product_parts.append(product.category.name_en)

        product_text = " ".join(product_parts)
        product_prompt = f"a photo of {product_text}"

        # Generar embedding del producto
        with torch.no_grad():
            prod_inputs = clip_processor(text=[product_prompt], return_tensors="pt", padding=True).to(device)
            prod_embedding = clip_model.get_text_features(**prod_inputs)
            prod_embedding = prod_embedding / prod_embedding.norm(dim=-1, keepdim=True)
            prod_vec = prod_embedding.cpu().numpy()[0]

        # Similitud coseno
        similarity = float(np.dot(query_vec, prod_vec))

        scored_candidates.append({
            'product': product,
            'similarity': similarity,
            'product_text': product_text
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


@bp.route("/search/text", methods=["POST", "OPTIONS"])
def text_search():
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

        cleaned_query = extraction_result.get('text', '')
        if cleaned_query and cleaned_query.strip() and extraction_result.get('success'):
            classification_done = False  # Flag para evitar doble clasificación contradictoria
            log_verbose(LogCategory.NLP, f"[TEXT_SEARCH] Preprocesamiento exitoso: '{query_text}' → '{cleaned_query}'")
            log_verbose(LogCategory.NLP, f"   📦 Categoría extraída: '{extraction_result.get('category')}'")
            log_verbose(LogCategory.NLP, f"   🏷️  Modificadores extraídos: {extraction_result.get('modifiers')}")

            # 🛑 PUNTO DE CORTE PARA TESTING
            # Obtener categorías del cliente
            try:
                client_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
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
                    from app.utils.semantic_colors import SYSTEM_COLOR_ADJECTIVES, map_semantic_colors, get_system_color_adjectives
                    # Detectar adjetivos sistémicos presentes en la query original (aunque no hayan quedado como modificadores)
                    nlp_colors = _get_nlp_es()
                    sys_color_tokens = []
                    if nlp_colors is not None:
                        doc_colors = nlp_colors(query_text)
                        for tok in doc_colors:
                            tl = tok.text.lower()
                            if tl in SYSTEM_COLOR_ADJECTIVES:
                                sys_color_tokens.append(tl)
                    if sys_color_tokens:
                        print(f"\n🎨 [SEMANTIC COLOR] Adjetivos sistémicos detectados en query: {sys_color_tokens}")
                        # Obtener lista de valores de color del cliente para similitud
                        from app.models.product_attribute_config import ProductAttributeConfig as _PAC_SM
                        color_cfg = _PAC_SM.query.filter_by(client_id=client.id, key='color').first()
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
                except Exception as e_sem_col:
                    print(f"[SEMANTIC COLOR] ⚠️ Error en mapeo semántico de colores: {e_sem_col}")

                # Cargar atributos configurados para este cliente
                from app.models.product_attribute_config import ProductAttributeConfig
                configured_attributes = ProductAttributeConfig.query.filter_by(
                    client_id=client.id
                ).order_by(ProductAttributeConfig.field_order).all()

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
                for mod in modificadores:
                    mod_norm = mod.strip().lower()

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
                        MIN_CATEGORY_RESULTS = 3
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
                MIN_CATEGORY_RESULTS = 3

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
                    # Query productos de las categorías detectadas
                    productos_en_categorias = Product.query.filter(
                        Product.client_id == client.id,
                        Product.category_id.in_(matched_category_ids),
                        Product.is_active == True
                    ).all()

                    productos_analizados = len(productos_en_categorias)
                    print(f"Total productos en categorías detectadas: {productos_analizados}")

                    # Extraer valores únicos de cada atributo configurado
                    for attr_config in configured_attributes:
                        key = attr_config.key
                        valores_unicos = set()

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

                # 🛑 RETORNAR AQUÍ PARA TESTING (JSON enriquecido con 'filtering.top_5_productos')
                try:
                    def _attr_exists(val):
                        if val is None:
                            return False
                        if isinstance(val, bool):
                            return bool(val)
                        if isinstance(val, (list, tuple, set, dict)):
                            return len(val) > 0
                        s = str(val).strip().lower()
                        return s not in ('', 'no', 'false', '0', 'none', 'null')

                    strong_attr_map = []
                    for a in (atributos_encontrados or []):
                        strong_attr_map.append({
                            'key': a.get('atributo_key'),
                            'label': a.get('atributo_label') or a.get('atributo_key')
                        })

                    try:
                        clip_scores  # noqa
                    except NameError:
                        clip_scores = {}

                    enriched_top5 = []
                    for p in (filtered_products[:5] if 'filtered_products' in locals() and filtered_products else []):
                        image_url = None
                        try:
                            primary_image = Image.query.filter_by(product_id=p.id, is_primary=True).first()
                            if not primary_image:
                                primary_image = Image.query.filter_by(product_id=p.id).first()
                            if primary_image:
                                image_url = primary_image.display_url  # TiendaNube source_url o Cloudinary
                        except Exception:
                            image_url = None

                        coverage = []
                        attrs = p.attributes or {}
                        for m in strong_attr_map:
                            key = (m.get('key') or '').strip()
                            label = (m.get('label') or key).strip()
                            val = attrs.get(key)
                            exists = _attr_exists(val)
                            coverage.append({
                                'key': key,
                                'label': label,
                                'exists': bool(exists),
                                'value': val
                            })

                        sim = float(clip_scores.get(p.id, 0.0)) if isinstance(clip_scores, dict) else 0.0
                        weak_applied = bool(modificadores_no_configurados) and sim > 0.50

                        has_strong = any(c.get('exists') for c in coverage) if coverage else False
                        if has_strong and weak_applied:
                            match_type = 'AMBOS'
                        elif has_strong:
                            match_type = 'FUERTE'
                        elif weak_applied:
                            match_type = 'DÉBIL'
                        else:
                            match_type = 'BASE'

                        enriched_top5.append({
                            'id': str(p.id),
                            'name': p.name,
                            'sku': p.sku,
                            'category': p.category.name if p.category else None,
                            'price': float(p.price) if p.price else None,
                            'stock': p.stock if hasattr(p, 'stock') else None,
                            'attributes': p.attributes or {},
                            'image_url': image_url,
                            'attributes_coverage': coverage,
                            'weak_modifiers': modificadores_no_configurados or [],
                            'clip_similarity': round(sim, 3) if sim else 0.0,
                            'match_type': match_type
                        })
                except Exception as _e:
                    print(f"⚠️ Enriquecimiento top_5 (bloque 2) falló: {_e}")
                    enriched_top5 = []

                try:
                    base_count = len(base_products)
                except Exception:
                    base_count = 0
                try:
                    final_count = len(filtered_products)
                except Exception:
                    final_count = 0

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

                # Definir helper local para normalizar categorías antes de usarlo en response_data
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

                response_data = {
                    "success": True,
                    "query_original": data.get('query', ''),
                    "query_normalizada": cleaned_query,
                    "extraction": {
                        "categoria": categoria_extraida,
                        "modificadores": modificadores
                    },
                    "detection": {
                        "categorias_cliente_total": len(client_categories),
                        "categorias_matched": [ _cat_to_dict(cat) for cat in (matched_categories or []) ],
                        "tiene_match": len(matched_categories) > 0
                    },
                    "analysis": {
                        "atributos_configurados_total": len(configured_attributes),
                        "atributos_encontrados": atributos_encontrados,
                        "modificadores_no_configurados": modificadores_no_configurados,
                        "valores_disponibles_por_atributo": atributos_valores_disponibles,
                        "productos_analizados": productos_analizados
                    },
                    "filtering": {
                        "productos_base": base_count,
                        "productos_post_fuerte": final_count if atributos_encontrados else base_count,
                        "productos_finales": final_count,
                        "filtrado_clip_aplicado": len(modificadores_no_configurados) > 0,
                        "top_5_productos": enriched_top5
                    },
                    "exposed_attribute_keys": exposed_attribute_keys,
                    "exposed_attribute_labels": exposed_attribute_labels,
                    "next_step": "Testing completado - Ver cobertura en servidor y UI de prueba"
                }

                # 📊 Registrar analytics también en este early return (fallback)
                try:
                    import time as _t
                    print(f"🔍 ANALYTICS (early/fallback): Iniciando registro de búsqueda para client={client.id}", flush=True)
                    cats_detected = [ (c.get('name') if isinstance(c, dict) else getattr(c, 'name', None)) for c in (matched_categories or []) ]
                    cats_detected = [c for c in cats_detected if c]
                    cats_matched = list({(getattr(p.category, 'name', None) or '') for p in (filtered_products or []) if getattr(p, 'category', None)}) if 'filtered_products' in locals() else []
                    cats_matched = [c for c in cats_matched if c]
                    cats_missing = [c for c in cats_detected if c not in cats_matched]

                    # Fase 1 fallback: mismas reglas que early
                    terms_extracted = [str(m).lower() for m in (modificadores or []) if str(m).strip()]
                    terms_matched = [
                        str(af.get('modificador_original')).lower()
                        for af in (atributos_encontrados or [])
                        if af.get('modificador_original')
                    ]
                    terms_unmatched = [str(m).lower() for m in (modificadores_no_configurados or []) if str(m).strip()]

                    had_results_flag = bool('filtered_products' in locals() and filtered_products)

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
                        results_count=len(filtered_products or []) if 'filtered_products' in locals() else 0,
                        had_results=had_results_flag,
                        response_time_ms=elapsed_ms
                    )
                    print(f"✅ ANALYTICS (early/fallback): SearchLog.log_search() completado", flush=True)
                except Exception as _log_e:
                    import traceback as _tb
                    print(f"❌ ANALYTICS (early/fallback) ERROR: {_log_e}", flush=True)
                    print(f"   Traceback: {_tb.format_exc()}", flush=True)

                _resp = jsonify(response_data)
                _resp.headers['Access-Control-Allow-Origin'] = '*'
                _resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                _resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
                return _resp

            except Exception as e:
                print(f"⚠️ Error en detección de categorías: {e}")
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
        candidates, detection_metadata = stage1_broad_recall(query_text, client.id, client_slug, top_n=50)

        # Guardar expanded_terms para la respuesta (ya se calculó en stage1)
        expanded_terms_cache = expand_query_with_synonyms(query_text, client.id, client_slug)

        # 🚫 VALIDACIÓN CRÍTICA: Si no hay categoría válida detectada, NO continuar
        if not detection_metadata or not detection_metadata.get('matched_categories'):
            # Obtener todas las categorías comercializables del cliente
            available_categories = Category.query.filter_by(client_id=client.id, is_active=True).all()
            available_names = [cat.name for cat in available_categories]
            # Mensaje especial para el usuario y datos para UI (chips "Buscando en:")
            user_feedback = {
                "message": f"La categoría solicitada no se encuentra entre las comercializables.",
                "has_results": False,
                "categories_available": available_names
            }
            # Incluir 'categories_searched' para que el frontend muestre chips tipo "Buscando en: ..."
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
                "categories_searched": available_names
            }
            response = jsonify(response_data)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
            return response

        if not candidates:
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
                "group_by_category": False
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

        try:
            requested_attrs = attr_info.get('attributes', {}) or {}
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
            try:
                from app.models.product_attribute_config import ProductAttributeConfig
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
            except Exception:
                pass

            raw_tokens = [t.strip(".,;:!?") for t in query_text.lower().split() if t.strip()]

            for tok in raw_tokens:
                if len(tok) < 3:
                    continue
                # Saltar si es una categoría conocida
                if tok in category_tokens:
                    continue
                # 🆕 Saltar si es un atributo configurado (evita interpretar "bolsillos" como color)
                if tok in configured_attr_tokens:
                    continue

                c = normalize_color(tok, client_id=client.id)
                if c:
                    detected_color_token = tok
                    detected_color_normalized = c
                    print(f"🎨 Color detectado: '{tok}' → '{c}'")
                    break

            # NO agregamos a requested_attrs aquí - se manejará en el filtrado
        except Exception as _e:
            print(f"⚠️ Inferencia semántica de color falló: {_e}")

        # STAGE 2: Precise Reranking (CLIP)
        # Si hay múltiples categorías hermanas detectadas, ampliamos el límite de rerank
        # para poder luego devolver hasta `limit` por categoría sin quedarnos cortos.
        try:
            detected_cats = 0
            if detection_metadata and isinstance(detection_metadata.get('matched_categories'), list):
                detected_cats = len(detection_metadata.get('matched_categories'))
            rerank_limit = limit * detected_cats if detected_cats and detected_cats > 1 else limit
        except Exception:
            rerank_limit = limit

        scored_results = stage2_precise_rerank(query_text, candidates, limit=rerank_limit)

        # Calcular cumplimiento de atributos por producto
        requested_attrs = attr_info.get('attributes', {})
        requested_count = int(attr_info.get('requested_count', 0))

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

            # Forzar base64 y loguear si falta
            try:
                if primary_image and not getattr(primary_image, 'base64_data', None):
                    from app.utils.logging_config import log_error
                    log_error(f"Imagen sin base64 en BD (text search): {primary_image.id} - regenerando")
                    from app.services.image_manager import image_manager
                    _ = image_manager.get_image_base64(primary_image)
            except Exception:
                pass

            # Si aún no hay base64, usar placeholder (NUNCA Cloudinary)
            try:
                if primary_image:
                    img_url_tmp = primary_image.base64_data
                    if not (img_url_tmp and img_url_tmp.startswith('data:image')):
                        from app.utils.logging_config import log_error
                        log_error(f"Respuesta (text) sin base64, usando placeholder. Producto={product.id} Imagen={primary_image.id if primary_image else 'NA'}")
                        # 1x1 PNG transparente
                        primary_image.base64_data = (
                            'data:image/png;base64,'
                            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
                        )
            except Exception:
                pass

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

        # 🔍 FILTRADO POR ATRIBUTOS SOLICITADOS
        # Si se solicitaron atributos, mostrar productos que cumplan:
        # - Si se pidió color: preferir coincidencia estricta por color
        # - En caso contrario: al menos 1 atributo solicitado
        if requested_count > 0:
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
                color_filter_value = str(requested_attrs.get(color_req_key, '')).lower()
            elif detected_color_normalized:
                color_filter_value = str(detected_color_normalized).lower()

            if color_filter_value:
                # Mantener una copia de todos los resultados antes del filtro de color
                pre_color_results = list(formatted_results)
                # Usar el token ORIGINAL detectado si existe, sino el valor normalizado
                color_search_token = detected_color_token if detected_color_token else color_filter_value
                color_value_normalized = color_filter_value

                print(f"🎨 Filtrando por color: token='{color_search_token}', normalizado='{color_value_normalized}'")

                # 1) Intentar coincidencias con el color NORMALIZADO en los atributos de productos
                exact_matches = [
                    r for r in formatted_results
                    if str(r.get('attributes', {}).get('color', '')).lower() == color_value_normalized
                ]

                if exact_matches:
                    filtered_results = exact_matches
                    matched_similar_color = color_value_normalized  # Hay match exacto
                    print(f"✅ Filtrado por color exacto '{color_value_normalized}': {len(exact_matches)} productos")
                else:
                    # 2) No hay exactos: buscar colores similares usando el TOKEN ORIGINAL
                    print(f"🔍 No hay color exacto, buscando similares a '{color_search_token}'...")
                    try:
                        from app.utils.colors import _get_color_embedding
                        # Calcular embedding del TOKEN ORIGINAL (ej: "grices")
                        target_emb = _get_color_embedding(color_search_token, client_id=client.id)
                        similar_colors = []

                        # Si no hay 'color' en all_available_values (porque no fue solicitado),
                        # no podremos sugerir similares; solo intentaremos exactos.
                        available_vals = all_available_values.get(color_req_key) if color_req_key else None
                        if target_emb is not None and available_vals:
                            available_product_colors = [str(v).lower() for v in available_vals]
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

                            # Ordenar y tomar top-3 con umbral 0.58 (permisivo para captar "grices"→"gris" sim=0.583)
                            scored.sort(key=lambda x: x[1], reverse=True)
                            THRESH = 0.58
                            TOPK = 3
                            similar_colors = [c for c, s in scored if s >= THRESH][:TOPK]
                            print(f"🎨 Colores similares a '{color_search_token}': {[(c,round(s,3)) for c,s in scored[:5]]}")
                            print(f"✅ Top similares (>{THRESH}): {similar_colors}")

                        if similar_colors:
                            similar_set = set(similar_colors)
                            filtered_results = [
                                r for r in formatted_results
                                if str(r.get('attributes', {}).get('color', '')).lower() in similar_set
                            ]
                            # 🎨 Guardar el mejor color similar encontrado
                            if similar_colors:
                                matched_similar_color = similar_colors[0]  # El más similar
                            print(f"✅ Filtrado por colores similares: {len(filtered_results)} productos")
                        else:
                            # 3) Sin similares: devolver vacío
                            filtered_results = []
                            print(f"❌ No se encontraron colores similares a '{color_search_token}'")
                    except Exception as e:
                        print(f"⚠️ Error buscando colores similares: {e}")
                        import traceback
                        traceback.print_exc()
                        filtered_results = []

                # 🎨 ACTUALIZAR requested_attrs con el color que realmente matcheó
                if matched_similar_color:
                    requested_attrs['color'] = matched_similar_color
                    # 🎯 ACTUALIZAR también detected_color_normalized para el feedback correcto
                    if detected_color_token:
                        detected_color_normalized = matched_similar_color
                    print(f"🎨 Color para matching actualizado: '{color_value_normalized}' → '{matched_similar_color}'")

                    # 🔄 RECALCULAR attributes_match_count con el color actualizado
                    for r in filtered_results:
                        prod_attrs = r.get('attributes', {})
                        matched = {}
                        for k, v in requested_attrs.items():
                            pv = prod_attrs.get(k)
                            if pv is None:
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

                # Si el filtrado por color deja pocos resultados, completar con fallbacks
                try:
                    # Objetivo total aproximado para mantener buen recall antes de agrupar
                    target_total = rerank_limit if 'rerank_limit' in locals() else limit
                    target_total = min(target_total, len(pre_color_results))
                except Exception:
                    target_total = len(pre_color_results)

                if len(filtered_results) < target_total:
                    needed = target_total - len(filtered_results)
                    # Mantener orden original, agregando productos que no pasaron el filtro de color
                    fallback_candidates = [r for r in pre_color_results if r not in filtered_results]
                    filtered_results.extend(fallback_candidates[:needed])

                formatted_results = filtered_results
            else:
                # Filtrar: mantener solo productos que cumplan AL MENOS 1 atributo solicitado
                filtered_results = [r for r in formatted_results if r.get("attributes_match_count", 0) > 0]
                # Para otros atributos, mantener fallback de no filtrar si quedaría vacío
                if filtered_results:
                    formatted_results = filtered_results

            # Reordenar: por cantidad de atributos cumplidos, luego stock, luego similitud
            # 🔄 PRIORIDAD: Productos no-fallback primero
            try:
                fallback_ids_set = fallback_product_ids  # Definido en el filtrado fuerte
            except NameError:
                fallback_ids_set = set()

            formatted_results.sort(
                key=lambda r: (
                    0 if r.get("id") in fallback_ids_set else 1,  # No-fallback=1 (primero), Fallback=0 (después)
                    r.get("attributes_match_count", 0),
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )
        else:
            # Si no hubo atributos solicitados, priorizar stock disponible y luego similitud
            all_available_values = {}
            formatted_results.sort(
                key=lambda r: (
                    1 if (r.get("stock") or 0) > 0 else 0,
                    r.get("similarity", 0.0)
                ),
                reverse=True
            )

        # Respuesta final
        elapsed = time.time() - start_time

        # MARCADOR TEMPRANO: Confirmar que el código llega aquí
        log_error(f"\n✅✅✅ BÚSQUEDA COMPLETADA - Punto A (ANTES de agrupación) ✅✅✅")
        log_error(f"   elapsed={elapsed:.3f}s")
        log_error(f"   formatted_results count: {len(formatted_results)}")
        log_error(f"   detection_metadata: {bool(detection_metadata)}")

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
            not_configured=attr_info.get('not_configured', []),
            all_available_values=all_available_values,  # Valores disponibles para los atributos filtrados
            detected_color_token=detected_color_token,  # Token original detectado como color
            detected_color_normalized=detected_color_normalized  # Color normalizado por LLM
        )

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
        MIN_CATEGORY_RESULTS = 3  # TOP 3 de cada categoría

        # LOG CRÍTICO: Diagnosticar por qué no se agrupa
        import sys
        sys.stderr.flush()
        sys.stdout.flush()

        log_error(f"\n🎯🎯🎯 AGRUPACIÓN - DIAGNÓSTICO CRÍTICO 🎯🎯🎯")
        log_error(f"   detection_metadata exists: {bool(detection_metadata)}")
        log_error(f"   detection_metadata type: {type(detection_metadata)}")
        if detection_metadata:
            log_error(f"   detection_metadata keys: {detection_metadata.keys() if isinstance(detection_metadata, dict) else 'N/A'}")
            matched_cats = detection_metadata.get('matched_categories', [])
            log_error(f"   matched_categories count: {len(matched_cats)}")
            log_error(f"   matched_categories: {matched_cats}")
        log_error(f"   formatted_results count: {len(formatted_results)}")
        log_error(f"   formatted_results sample: {formatted_results[:2] if formatted_results else 'EMPTY'}")

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
            cats_detected = [c['name'] for c in detection_metadata.get('matched_categories', [])] if detection_metadata else []
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
            log_error(f"❌ ERROR logging analytics: {log_err}")
            log_error(f"   Traceback: {traceback.format_exc()}")

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
