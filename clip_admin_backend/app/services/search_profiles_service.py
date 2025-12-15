"""
Servicio de Perfiles de Búsqueda por Industria

Define y administra reglas de normalización, expansión y detección de categoría por industria.
Cada perfil es un conjunto de reglas que se aplican por `client.industry`, con posibilidad de overrides por cliente.

Estructura:
- Perfil base (industry): variants_map, category_synonyms, color_tokens, name_en_ignore, filter_strategy
- Overrides por cliente: Guardados en Client.integration_config.search_rules
- Cache: En memoria con TTL de 1 hora
"""

import json
import hashlib
import os
from typing import Dict, List, Optional, Set, Tuple
from app import db
import logging

logger = logging.getLogger(__name__)

# Cache en memoria simple (sin Redis)
_profile_cache = {}  # client_id -> profile
_cache_timestamps = {}  # client_id -> timestamp

# spaCy (lemmatización española) - carga perezosa para evitar overhead si falta el modelo
_spacy_nlp = None
_SPACY_MODEL = os.getenv("SPACY_MODEL", "es_core_news_sm")


def _load_spacy_model():
    global _spacy_nlp
    if _spacy_nlp is not None:
        return _spacy_nlp
    try:
        import spacy

        _spacy_nlp = spacy.load(_SPACY_MODEL, disable=["ner", "textcat"])
        logger.info(f"spaCy cargado para perfiles de búsqueda: {_SPACY_MODEL}")
    except Exception as e:
        logger.warning(f"No se pudo cargar spaCy ({_SPACY_MODEL}). Se usará fallback simple. Detalle: {e}")
        _spacy_nlp = None
    return _spacy_nlp


# ============================================================================
# PERFILES PREDEFINIDOS POR INDUSTRIA
# ============================================================================

DEFAULT_PROFILES = {
    "fashion": {
        "name": "Moda / Fashion",
        "description": "Perfil para tiendas de ropa, accesorios y textiles",
        "variants_map": {
            # Variaciones ortográficas
            "shore": "short",
            "shores": "short",
            # Sinónimos de dominio
            "camiseta": "remera",
            "polera": "remera",
            "top": "remera",
            "jean": "pantalon",
            "jeans": "pantalon",
            "pant": "pantalon",
            "saco": "chaqueta",
            "blazer": "chaqueta",
            "campera": "abrigo",
            "chamarra": "abrigo",
            "buzo": "sweater",
            "gorro": "gorra",
            "cap": "gorra",
            "bota": "zapato",
            "calzado": "zapato",
            "sandalia": "zapato",
            "cartera": "bolso",
        },
        "category_synonyms": {
            "short": ["shore", "shores", "shorts"],
            "remera": ["camiseta", "polera", "top"],
            "pantalon": ["jean", "jeans", "pant"],
            "bermuda": ["bermudas"],
            "falda": ["faldas"],
            "vestido": ["vestidos"],
            "chaqueta": ["saco", "blazer"],
            "abrigo": ["campera", "chamarra"],
            "sweater": ["buzo"],
            "gorra": ["gorro", "cap"],
            "zapato": ["bota", "sandalia", "calzado"],
            "bolso": ["cartera"],
        },
        "color_tokens": {
            "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
            "beige", "rosa", "amarillo", "violeta", "celeste", "naranja",
            "plateado", "dorado", "plateado", "plateados", "dorados",
            "turquesa", "fucsia", "bordeaux", "vino", "militar",
        },
        "name_en_ignore_modifiers": {
            "short", "long", "high", "low", "rise", "sleeve", "neck", "casual",
            "formal", "sport", "party", "work", "beach", "summer", "winter",
        },
        "filter_strategy": "root-unique",  # "root-unique" o "broad"
    },
    "uniforms": {
        "name": "Uniformes / Ropa de Trabajo",
        "description": "Perfil para uniformes corporativos y ropa de trabajo",
        "variants_map": {
            # Sinónimos de dominio
            "mandil": "delantal",
            "uniforme": "ambo",
            "casaca": "chaqueta",
            "chamarra": "chaqueta",
            "sudadera": "buzo",
            "rebeca": "cardigan",
            "gorra": "gorro",
            "cap": "gorro",
            "calzado": "zapato",
        },
        "category_synonyms": {
            "delantal": ["mandil", "delantales"],
            "ambo": ["uniforme", "uniformes"],
            "camisa": ["camisas"],
            "chaqueta": ["chaquetas", "casaca", "casacas", "chamarra"],
            "buzo": ["buzos", "sudadera"],
            "cardigan": ["cardigans", "rebeca"],
            "chaleco": ["chalecos"],
            "gorro": ["gorros", "gorra", "gorras", "cap"],
            "zapato": ["zapatos", "calzado"],
            "zueco": ["zuecos"],
        },
        "color_tokens": {
            "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
            "beige", "rosa", "amarillo", "violeta", "celeste", "naranja",
            "plateado", "caramelo", "turquesa", "fucsia",
        },
        "name_en_ignore_modifiers": {
            "short", "long", "high", "low", "rise", "sleeve", "neck",
        },
        "filter_strategy": "root-unique",
    },
    "generic": {
        "name": "Genérico",
        "description": "Perfil genérico para otros rubros",
        "variants_map": {},
        "category_synonyms": {},
        "color_tokens": {
            "rojo", "verde", "azul", "negro", "blanco", "marron", "gris",
            "beige", "rosa", "amarillo", "violeta", "celeste", "naranja",
        },
        "name_en_ignore_modifiers": set(),
        "filter_strategy": "broad",
    },
}


class SearchProfilesService:
    """Servicio para cargar, cachear y aplicar perfiles de búsqueda."""

    CACHE_TTL = 3600  # 1 hora

    @staticmethod
    def get_profile(client_id: str, client_industry: str = None, force_reload: bool = False) -> Dict:
        """
        Obtiene el perfil de búsqueda para un cliente.

        Prioridad:
        1. Overrides específicos del cliente (Client.integration_config.search_rules)
        2. Perfil por industria (client.industry)
        3. Perfil genérico

        Args:
            client_id: ID del cliente
            client_industry: Industria del cliente (para evitar query si ya la tenemos)
            force_reload: Forzar recarga sin cache

        Returns:
            Dict con reglas de búsqueda (variants_map, category_synonyms, etc.)
        """
        import time

        # Intentar obtener del cache en memoria
        cache_key = client_id
        if not force_reload and cache_key in _profile_cache:
            # Verificar TTL (CACHE_TTL = 3600 segundos)
            if time.time() - _cache_timestamps.get(cache_key, 0) < SearchProfilesService.CACHE_TTL:
                return _profile_cache[cache_key]
            else:
                # Cache expirado, eliminarlo
                del _profile_cache[cache_key]
                del _cache_timestamps[cache_key]

        # Si no tenemos industry, obtenerla de BD
        if not client_industry:
            from app.models.client import Client
            client = Client.query.get(client_id)
            if not client:
                logger.warning(f"Cliente {client_id} no encontrado")
                client_industry = "generic"
            else:
                client_industry = client.industry or "generic"

        # Obtener perfil base por industria
        base_profile = DEFAULT_PROFILES.get(client_industry or "generic", DEFAULT_PROFILES["generic"]).copy()

        # Cargar overrides del cliente
        try:
            from app.models.client import Client
            client = Client.query.get(client_id)
            if client and client.integration_config:
                overrides = client.integration_config.get("search_rules", {})
                if overrides:
                    # Mergear overrides con el perfil base
                    base_profile = SearchProfilesService._merge_profiles(base_profile, overrides)
                    logger.info(f"Perfil para {client_id} ({client_industry}) con {len(overrides)} overrides")
        except Exception as e:
            logger.warning(f"Error cargando overrides para {client_id}: {e}")

        # Cachear resultado en memoria
        _profile_cache[cache_key] = base_profile
        _cache_timestamps[cache_key] = time.time()

        return base_profile

    @staticmethod
    def _merge_profiles(base: Dict, overrides: Dict) -> Dict:
        """Mergea un perfil base con overrides, sin perder claves base."""
        merged = base.copy()

        if "variants_map" in overrides:
            merged["variants_map"] = {**merged.get("variants_map", {}), **overrides["variants_map"]}
        if "category_synonyms" in overrides:
            merged["category_synonyms"] = {**merged.get("category_synonyms", {}), **overrides["category_synonyms"]}
        if "color_tokens" in overrides:
            merged["color_tokens"] = set(merged.get("color_tokens", [])) | set(overrides["color_tokens"])
        if "name_en_ignore_modifiers" in overrides:
            merged["name_en_ignore_modifiers"] = set(merged.get("name_en_ignore_modifiers", [])) | set(
                overrides["name_en_ignore_modifiers"]
            )
        if "filter_strategy" in overrides:
            merged["filter_strategy"] = overrides["filter_strategy"]

        return merged

    @staticmethod
    def normalize_tokens(text: str, profile: Dict) -> List[str]:
        """Normaliza tokens usando spaCy (si está disponible) + variantes del perfil."""
        if not text:
            return []

        variants_map = profile.get("variants_map", {})
        stop_tokens = {"de", "del", "la", "el", "y", "con", "sin", "en", "un", "una", "unos", "unas", "lo", "al"}

        tokens: List[str] = []
        nlp = _load_spacy_model()
        if nlp:
            try:
                doc = nlp(text.lower())
                tokens = [t.lemma_.lower() if t.lemma_ else t.text.lower() for t in doc if t.is_alpha]
            except Exception as e:
                logger.warning(f"Fallo spaCy en normalize_tokens, usando fallback simple: {e}")
                tokens = []

        if not tokens:
            tokens = text.lower().replace("-", " ").replace("_", " ").split()

        normalized = []
        for token in tokens:
            clean_token = "".join(c for c in token if c.isalpha())
            if not clean_token:
                continue

            mapped_token = variants_map.get(clean_token, clean_token)
            if mapped_token not in stop_tokens:
                normalized.append(mapped_token)

        return normalized

    @staticmethod
    def expand_query(query_text: str, categories, profile: Dict) -> List[str]:
        """Expande query con sinónimos del perfil y alternative_terms de BD."""
        tokens = SearchProfilesService.normalize_tokens(query_text, profile)
        expanded = set(tokens)

        # Agregar sinónimos del perfil
        category_synonyms = profile.get("category_synonyms", {})
        for token in tokens:
            if token in category_synonyms:
                expanded.update(category_synonyms[token])

        # Agregar alternative_terms de categorías
        for cat in categories:
            if not cat.alternative_terms:
                continue

            cat_synonyms = [s.strip() for s in cat.alternative_terms.split(",") if s.strip()]
            normalized_synonyms = [
                SearchProfilesService.normalize_tokens(syn, profile)[0]
                for syn in cat_synonyms
                if SearchProfilesService.normalize_tokens(syn, profile)
            ]

            if any(token in normalized_synonyms for token in tokens):
                expanded.update(normalized_synonyms)

        result = list(expanded)
        logger.debug(f"Query expandida: '{query_text}' → {len(result)} términos")
        return result

    @staticmethod
    def detect_category_filter(query_tokens: List[str], categories, profile: Dict) -> Tuple[Optional[List], Dict]:
        """
        Detecta si el query menciona categoría y retorna IDs para filtrar + metadata.

        Estrategia:
        - "root-unique": Solo filtra si hay UN ÚNICO token del query que matchea categoría
        - "broad": Filtra si hay cualquier match (menos restrictivo)

        Returns:
            (category_ids, detection_metadata) o (None, None)
        """
        color_tokens = profile.get("color_tokens", set())
        filter_strategy = profile.get("filter_strategy", "root-unique")
        name_en_ignore = profile.get("name_en_ignore_modifiers", set())

        # Filtrar colores del query
        filtered_tokens = [t for t in query_tokens if t not in color_tokens]

        if not filtered_tokens:
            return None, None

        # Construir tokens por categoría
        category_tokens_map = {}
        for cat in categories:
            cat_tokens = set()

            # Nombre: normalizado con variants_map
            if cat.name:
                cat_tokens.update(SearchProfilesService.normalize_tokens(cat.name, profile))

            # name_en: solo tokens clave (ignorar modificadores)
            if cat.name_en:
                name_en_tokens = cat.name_en.strip().lower().split()
                for token in name_en_tokens:
                    if token not in name_en_ignore:
                        cat_tokens.add(token)

            # alternative_terms: sin normalizar (solo lowercase + split)
            if cat.alternative_terms:
                for term in cat.alternative_terms.split(","):
                    cat_tokens.update(term.strip().lower().split())

            category_tokens_map[cat.id] = (cat_tokens, cat.name)

        # Detectar matches
        matched = []
        for cat_id, (cat_tokens, cat_name) in category_tokens_map.items():
            for query_token in filtered_tokens:
                if query_token in cat_tokens:
                    matched.append((cat_id, query_token, cat_name))
                    break

        if not matched:
            return None, None

        # Agrupar por token del query
        token_to_cats = {}
        for cat_id, matched_token, cat_name in matched:
            token_to_cats.setdefault(matched_token, []).append((cat_id, cat_name))

        # Aplicar estrategia
        if filter_strategy == "root-unique":
            # Solo si un token único
            if len(token_to_cats) == 1:
                sole_token = next(iter(token_to_cats.keys()))
                category_info = token_to_cats[sole_token]
                category_ids = [cat_id for cat_id, _ in category_info]
                cat_names = [cat_name for _, cat_name in category_info]

                return category_ids, {
                    "requested_term": sole_token,
                    "matched_categories": cat_names,
                    "match_type": "category_filter",
                }
            else:
                return None, None
        else:
            # "broad": devolver todos los matches
            all_cat_ids = set()
            all_cat_names = set()
            for token, cat_list in token_to_cats.items():
                all_cat_ids.update([cat_id for cat_id, _ in cat_list])
                all_cat_names.update([cat_name for _, cat_name in cat_list])

            return list(all_cat_ids), {
                "requested_tokens": list(token_to_cats.keys()),
                "matched_categories": list(all_cat_names),
                "match_type": "category_filter_broad",
            }

    @staticmethod
    def save_client_overrides(client_id: str, overrides: Dict) -> bool:
        """
        Guarda overrides para un cliente específico.

        Args:
            client_id: ID del cliente
            overrides: Dict con search_rules (partial merge sobre el perfil base)

        Returns:
            True si éxito, False si error
        """
        try:
            from app.models.client import Client

            client = Client.query.get(client_id)
            if not client:
                logger.error(f"Cliente {client_id} no encontrado")
                return False

            if not client.integration_config:
                client.integration_config = {}

            client.integration_config["search_rules"] = overrides
            client.updated_at = db.func.now()

            db.session.add(client)
            db.session.commit()

            # Invalidar cache en memoria
            if client_id in _profile_cache:
                del _profile_cache[client_id]
            if client_id in _cache_timestamps:
                del _cache_timestamps[client_id]

            logger.info(f"Overrides guardados para {client_id}")
            return True
        except Exception as e:
            logger.error(f"Error guardando overrides para {client_id}: {e}")
            db.session.rollback()
            return False
    @staticmethod
    def get_all_profiles() -> Dict:
        """Retorna todos los perfiles disponibles (metadatos sin reglas completas)."""
        return {
            slug: {"name": prof["name"], "description": prof.get("description", "")}
            for slug, prof in DEFAULT_PROFILES.items()
        }
