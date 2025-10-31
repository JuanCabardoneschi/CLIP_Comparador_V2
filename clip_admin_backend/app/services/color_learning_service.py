"""
Servicio de aprendizaje de colores: integra ColorMapping con el sistema de búsqueda
"""
from app.models import ColorMapping
from app.utils.llm_query_normalizer import normalize_query
from app.utils.colors import normalize_color, colors_are_similar, SIMILAR_COLOR_GROUPS
import logging

logger = logging.getLogger(__name__)


class ColorLearningService:
    """
    Servicio que gestiona el aprendizaje automático de colores por cliente.

    Flujo:
    1. Cuando se procesa un color, busca en la BD del cliente
    2. Si existe → uso instantáneo
    3. Si no existe → normaliza con LLM y guarda
    4. Detecta grupos de similitud automáticamente
    """

    @staticmethod
    def process_color(client_id, raw_color, auto_group=True):
        """
        Procesa un color: obtiene mapeo existente o crea uno nuevo.

        Args:
            client_id: UUID del cliente
            raw_color: Color tal como viene del producto
            auto_group: Si es True, intenta asignar automáticamente a un grupo

        Returns:
            {
                'raw_color': str,
                'normalized_color': str,
                'similarity_group': str o None,
                'is_new': bool,
                'confidence': float o None
            }
        """
        if not raw_color:
            return None

        # Limpiar color
        clean_color = raw_color.strip()

        # Buscar mapeo existente
        mapping = ColorMapping.query.filter_by(
            client_id=client_id,
            raw_color=clean_color
        ).first()

        if mapping:
            # Mapeo existente → incrementar uso
            logger.info(f"✅ Color conocido: '{clean_color}' → {mapping.normalized_color} (grupo: {mapping.similarity_group}, usos: {mapping.usage_count})")

            ColorMapping.get_or_create(
                client_id=client_id,
                raw_color=clean_color
            )

            return {
                'raw_color': clean_color,
                'normalized_color': mapping.normalized_color,
                'similarity_group': mapping.similarity_group,
                'is_new': False,
                'confidence': mapping.confidence
            }
        else:
            # Color nuevo → normalizar y crear mapeo
            logger.info(f"🆕 Color nuevo: '{clean_color}' → normalizando...")

            # 1. Normalizar con el sistema actual (hardcoded + LLM)
            normalized = normalize_color(clean_color)

            # 2. Buscar grupo de similitud
            similarity_group = None

            if auto_group:
                similarity_group = ColorLearningService._find_similarity_group(
                    client_id=client_id,
                    normalized_color=normalized
                )

            # 3. Guardar mapeo
            confidence = None  # TODO: obtener confidence del LLM

            mapping = ColorMapping.get_or_create(
                client_id=client_id,
                raw_color=clean_color,
                normalized_color=normalized,
                similarity_group=similarity_group,
                confidence=confidence
            )

            logger.info(f"💾 Color guardado: '{clean_color}' → {normalized} (grupo: {similarity_group})")

            return {
                'raw_color': clean_color,
                'normalized_color': normalized,
                'similarity_group': similarity_group,
                'is_new': True,
                'confidence': confidence
            }

    @staticmethod
    def _find_similarity_group(client_id, normalized_color):
        """
        Busca a qué grupo de similitud pertenece un color normalizado.

        Prioridad:
        1. Grupos hardcoded globales (SIMILAR_COLOR_GROUPS)
        2. Grupos aprendidos del cliente
        3. El color normalizado se convierte en su propio grupo

        Args:
            client_id: UUID del cliente
            normalized_color: Color normalizado (ej: "AZUL", "CORAL")

        Returns:
            str: Nombre del grupo de similitud
        """
        # 1. Buscar en grupos hardcoded globales
        for group in SIMILAR_COLOR_GROUPS:
            if normalized_color in group:
                # Retornar el primer color del grupo (por convención)
                return sorted(group)[0]

        # 2. Buscar en grupos aprendidos del cliente
        client_groups = ColorMapping.get_client_color_groups(client_id)

        for group_name, mappings in client_groups['groups'].items():
            for mapping in mappings:
                if colors_are_similar(normalized_color, mapping.normalized_color):
                    logger.info(f"📚 Color '{normalized_color}' asignado al grupo existente '{group_name}'")
                    return group_name

        # 3. No encontró grupo → el color normalizado es su propio grupo
        logger.info(f"🎨 Color '{normalized_color}' crea su propio grupo")
        return normalized_color

    @staticmethod
    def get_similar_colors_for_search(client_id, detected_color):
        """
        Obtiene todos los colores raw que deberían matchear con un color detectado.
        Útil para aplicar boost en búsquedas.

        Args:
            client_id: UUID del cliente
            detected_color: Color detectado por CLIP o normalizado por LLM

        Returns:
            Lista de strings con raw_colors que deberían matchear
        """
        # Normalizar el color detectado
        normalized = normalize_color(detected_color)

        # Buscar a qué grupo pertenece
        similarity_group = ColorLearningService._find_similarity_group(client_id, normalized)

        if not similarity_group:
            return [detected_color]

        # Obtener todos los raw_colors de ese grupo
        raw_colors = ColorMapping.get_colors_in_group(client_id, similarity_group)

        if raw_colors:
            logger.debug(f"🔍 Color '{detected_color}' → grupo '{similarity_group}' → {len(raw_colors)} colores raw")
            return raw_colors
        else:
            return [detected_color]

    @staticmethod
    def suggest_color_groups(client_id, min_usage=2):
        """
        Sugiere agrupaciones de colores basándose en similitud LLM.
        Útil para mostrar en el panel de administración.

        Args:
            client_id: UUID del cliente
            min_usage: Mínimo de usos para considerar el color

        Returns:
            Lista de sugerencias:
            [
                {
                    'colors': ['coral vibrante', 'salmón'],
                    'suggested_group': 'NARANJA',
                    'confidence': 0.87
                }
            ]
        """
        # Obtener colores sin grupo del cliente
        client_data = ColorMapping.get_client_color_groups(client_id)
        ungrouped = [m for m in client_data['ungrouped'] if m.usage_count >= min_usage]

        suggestions = []

        # Comparar cada color sin grupo con todos los grupos existentes
        for mapping in ungrouped:
            best_match = None
            best_similarity = 0.0

            for group_name, group_mappings in client_data['groups'].items():
                for group_mapping in group_mappings:
                    # TODO: calcular similitud real con embeddings
                    if colors_are_similar(mapping.normalized_color, group_mapping.normalized_color):
                        similarity = 0.85  # Placeholder
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = group_name

            if best_match and best_similarity >= 0.75:
                suggestions.append({
                    'color': mapping.raw_color,
                    'suggested_group': best_match,
                    'confidence': best_similarity
                })

        return suggestions

    @staticmethod
    def merge_colors_into_group(client_id, raw_colors, group_name):
        """
        Agrupa manualmente varios colores en un mismo similarity_group.

        Args:
            client_id: UUID del cliente
            raw_colors: Lista de raw_colors a agrupar
            group_name: Nombre del grupo

        Returns:
            int: Número de colores actualizados
        """
        updated = 0

        for raw_color in raw_colors:
            mapping = ColorMapping.query.filter_by(
                client_id=client_id,
                raw_color=raw_color
            ).first()

            if mapping:
                mapping.similarity_group = group_name
                mapping.extra_metadata = (mapping.extra_metadata or {})
                mapping.extra_metadata['manual_grouping'] = True
                updated += 1

        from app import db
        db.session.commit()

        logger.info(f"✅ Agrupados {updated} colores en '{group_name}' para cliente {client_id}")
        return updated
