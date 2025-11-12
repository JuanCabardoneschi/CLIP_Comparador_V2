"""
Servicio de Conversación Inteligente
Maneja diálogos multi-turno usando MiniLM local (sin APIs externas).
"""
from typing import Dict, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ConversacionService:
    """Maneja conversaciones contextuales usando embeddings locales"""

    def __init__(self):
        self.model = None
        self._intent_templates = {
            'saludo': [
                'hola', 'buenos días', 'buenas tardes', 'buenas noches',
                'buen día', 'qué tal', 'saludos', 'hey', 'holi'
            ],
            'busqueda_general': [
                'busco', 'necesito', 'quiero', 'estoy buscando', 'me interesa',
                'quisiera', 'requiero', 'me hace falta', 'mostrame', 'dame'
            ],
            'busqueda_especifica': [
                'delantal rojo', 'gorra azul', 'uniforme de chef',
                'camisa blanca', 'pantalón negro', 'zapatos antideslizantes'
            ],
            'refinamiento': [
                'más barato', 'más caro', 'otro color', 'otra talla',
                'diferente', 'similar pero', 'parecido', 'alternativa'
            ],
            'multi_categoria': [
                'outfit completo', 'conjunto', 'uniforme completo',
                'todo para', 'vestimenta completa', 'equipo completo'
            ],
            'despedida': [
                'gracias', 'listo', 'perfecto', 'eso es todo',
                'nada más', 'chau', 'adiós', 'hasta luego'
            ]
        }

    def get_model(self):
        """Lazy load del modelo MiniLM (ya instalado)"""
        if self.model is None:
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return self.model

    def detectar_intent(self, query: str) -> Tuple[str, float]:
        """
        Detecta la intención del usuario usando embeddings
        Returns: (intent_name, confidence_score)
        """
        query_lower = query.lower().strip()

        # Reglas rápidas primero (sin embeddings)
        if len(query_lower) < 3:
            return 'saludo', 0.5

        # Detectar saludos sin palabras clave de búsqueda
        palabras_query = query_lower.split()
        es_solo_saludo = any(s in query_lower for s in ['hola', 'buenos', 'buenas', 'buen día'])
        tiene_busqueda = any(b in query_lower for b in ['busco', 'necesito', 'quiero', 'mostrame'])

        if es_solo_saludo and not tiene_busqueda:
            return 'saludo', 0.95

        # Detectar multi-categoría
        if any(m in query_lower for m in ['outfit', 'conjunto', 'completo', 'uniforme completo']):
            return 'multi_categoria', 0.9

        # Detectar refinamiento
        if any(r in query_lower for r in ['más', 'otro', 'diferente', 'similar', 'parecido']):
            return 'refinamiento', 0.85

        # Detectar despedida
        if query_lower in ['gracias', 'listo', 'perfecto', 'eso es todo', 'nada más', 'chau']:
            return 'despedida', 0.95

        # Para el resto, usar embeddings
        model = self.get_model()
        query_emb = model.encode([query_lower])[0]

        best_intent = 'busqueda_general'
        best_score = 0.0

        for intent, templates in self._intent_templates.items():
            template_embs = model.encode(templates)
            similarities = cosine_similarity([query_emb], template_embs)[0]
            max_sim = float(np.max(similarities))

            if max_sim > best_score:
                best_score = max_sim
                best_intent = intent

        # Si no hay match claro, es búsqueda general
        if best_score < 0.4:
            best_intent = 'busqueda_general'
            best_score = 0.6

        return best_intent, best_score

    def generar_respuesta_contextual(
        self,
        query: str,
        intent: str,
        historial: List[Dict],
        client_info: Optional[Dict] = None
    ) -> Dict:
        """
        Genera respuesta conversacional basada en intent y contexto

        Returns: {
            'mensaje': str,  # Respuesta del asistente
            'necesita_clarificacion': bool,
            'preguntas_sugeridas': List[str],
            'continuar_busqueda': bool
        }
        """
        es_primera_interaccion = len(historial) == 0

        # Personalización por tipo de cliente (opcional)
        tono = 'formal'
        if client_info:
            business_type = client_info.get('business_type', '').lower()
            if 'gastronomi' in business_type or 'cafe' in business_type:
                tono = 'amigable'
            elif 'moda' in business_type or 'retail' in business_type:
                tono = 'casual'

        # Generar respuesta según intent
        if intent == 'saludo':
            return self._respuesta_saludo(tono, es_primera_interaccion)
        elif intent == 'busqueda_general':
            return self._respuesta_busqueda_general(query, historial)
        elif intent == 'busqueda_especifica':
            return self._respuesta_busqueda_especifica(query)
        elif intent == 'multi_categoria':
            return self._respuesta_multi_categoria(query, historial)
        elif intent == 'refinamiento':
            return self._respuesta_refinamiento(query, historial)
        elif intent == 'despedida':
            return self._respuesta_despedida(tono)
        else:
            return self._respuesta_default()

    def _respuesta_saludo(self, tono: str, es_primera: bool) -> Dict:
        """Respuesta a saludos"""
        if tono == 'amigable':
            mensajes = [
                '¡Hola! ¿En qué te puedo ayudar hoy?',
                '¡Buen día! ¿Qué estás buscando?',
                '¡Hola! ¿Buscás algo en particular?'
            ]
        elif tono == 'casual':
            mensajes = [
                'Hey! ¿Qué necesitás?',
                'Hola! ¿En qué te ayudo?',
                '¡Hola! ¿Qué buscás?'
            ]
        else:  # formal
            mensajes = [
                'Buenos días. ¿En qué puedo asistirle?',
                'Bienvenido. ¿Qué producto está buscando?',
                'Hola. ¿Cómo puedo ayudarle hoy?'
            ]

        import random
        mensaje = random.choice(mensajes)

        return {
            'mensaje': mensaje,
            'necesita_clarificacion': False,
            'preguntas_sugeridas': [
                '¿Buscás algo específico?',
                '¿Qué tipo de producto te interesa?'
            ],
            'continuar_busqueda': False
        }

    def _respuesta_busqueda_general(self, query: str, historial: List) -> Dict:
        """Respuesta a búsquedas generales que necesitan clarificación"""
        query_lower = query.lower()

        # Detectar qué información falta
        tiene_categoria = any(cat in query_lower for cat in [
            'delantal', 'gorra', 'camisa', 'pantalón', 'uniforme', 'zapato'
        ])
        tiene_color = any(col in query_lower for col in [
            'rojo', 'azul', 'negro', 'blanco', 'verde', 'amarillo', 'gris'
        ])

        preguntas = []
        if not tiene_categoria:
            preguntas.append('¿Qué tipo de producto buscás? (delantal, gorra, camisa, etc.)')
        if not tiene_color:
            preguntas.append('¿Tenés algún color en mente?')

        if preguntas:
            mensaje = f'Claro, te ayudo a buscar. {preguntas[0]}'
        else:
            mensaje = 'Perfecto, buscando productos para vos...'

        return {
            'mensaje': mensaje,
            'necesita_clarificacion': len(preguntas) > 0,
            'preguntas_sugeridas': preguntas,
            'continuar_busqueda': len(preguntas) == 0
        }

    def _respuesta_busqueda_especifica(self, query: str) -> Dict:
        """Respuesta a búsquedas específicas (ya tiene categoría + atributos)"""
        return {
            'mensaje': 'Buscando productos que coincidan con tu descripción...',
            'necesita_clarificacion': False,
            'preguntas_sugeridas': [],
            'continuar_busqueda': True
        }

    def _respuesta_multi_categoria(self, query: str, historial: List) -> Dict:
        """Respuesta a búsquedas de múltiples categorías (outfit completo)"""
        query_lower = query.lower()

        # Detectar contexto
        contexto = None
        if 'chef' in query_lower or 'cocina' in query_lower:
            contexto = 'chef'
        elif 'bar' in query_lower or 'camarero' in query_lower:
            contexto = 'bar'
        elif 'cafe' in query_lower or 'barista' in query_lower:
            contexto = 'cafe'

        if contexto:
            mensaje = f'Entendido, buscando un outfit completo para {contexto}. Voy a mostrarte las mejores opciones en cada categoría.'
        else:
            mensaje = 'Perfecto, te voy a mostrar un conjunto completo. ¿Para qué tipo de trabajo es? (chef, café, bar, etc.)'
            return {
                'mensaje': mensaje,
                'necesita_clarificacion': True,
                'preguntas_sugeridas': ['¿Para qué trabajo es el uniforme?'],
                'continuar_busqueda': False
            }

        return {
            'mensaje': mensaje,
            'necesita_clarificacion': False,
            'preguntas_sugeridas': [],
            'continuar_busqueda': True
        }

    def _respuesta_refinamiento(self, query: str, historial: List) -> Dict:
        """Respuesta a refinamientos de búsqueda previa"""
        if not historial:
            return self._respuesta_busqueda_general(query, historial)

        query_lower = query.lower()

        if 'más barato' in query_lower or 'más económico' in query_lower:
            mensaje = 'Claro, te muestro opciones más económicas...'
        elif 'más caro' in query_lower or 'mejor calidad' in query_lower:
            mensaje = 'Perfecto, te muestro productos premium...'
        elif 'otro color' in query_lower or 'diferente color' in query_lower:
            mensaje = '¿Qué color preferís?'
            return {
                'mensaje': mensaje,
                'necesita_clarificacion': True,
                'preguntas_sugeridas': ['¿Qué color te gustaría?'],
                'continuar_busqueda': False
            }
        else:
            mensaje = 'Ajustando la búsqueda según tu preferencia...'

        return {
            'mensaje': mensaje,
            'necesita_clarificacion': False,
            'preguntas_sugeridas': [],
            'continuar_busqueda': True
        }

    def _respuesta_despedida(self, tono: str) -> Dict:
        """Respuesta a despedidas"""
        if tono == 'amigable':
            mensaje = '¡De nada! Si necesitás algo más, acá estoy.'
        elif tono == 'casual':
            mensaje = '¡Dale! Cualquier cosa me preguntás.'
        else:
            mensaje = 'Gracias por su consulta. Que tenga un buen día.'

        return {
            'mensaje': mensaje,
            'necesita_clarificacion': False,
            'preguntas_sugeridas': [],
            'continuar_busqueda': False
        }

    def _respuesta_default(self) -> Dict:
        """Respuesta por defecto"""
        return {
            'mensaje': 'Disculpá, no entendí bien. ¿Podrías reformular tu pregunta?',
            'necesita_clarificacion': True,
            'preguntas_sugeridas': ['¿Qué producto estás buscando?'],
            'continuar_busqueda': False
        }

    def agregar_sugerencias_post_busqueda(
        self,
        resultados: List[Dict],
        query_original: str,
        client_info: Optional[Dict] = None
    ) -> List[str]:
        """
        Genera sugerencias proactivas después de mostrar resultados

        Args:
            resultados: Lista de productos encontrados
            query_original: Query del usuario
            client_info: Info del cliente (opcional)

        Returns:
            Lista de sugerencias conversacionales
        """
        sugerencias = []

        if not resultados:
            sugerencias.append('No encontré resultados exactos. ¿Querés probar con otro color o categoría?')
            return sugerencias

        # Analizar resultados
        categorias = set(r.get('category', '') for r in resultados[:5])
        colores = set(r.get('color', '') for r in resultados[:5] if r.get('color'))
        precios = [r.get('precio', 0) for r in resultados[:5]]
        precio_promedio = sum(precios) / len(precios) if precios else 0

        # Sugerencias según contexto
        if len(categorias) == 1:
            cat = list(categorias)[0]
            sugerencias.append(f'¿Necesitás algo más para complementar tu {cat}?')

        if len(colores) > 2:
            sugerencias.append(f'Encontré {len(colores)} colores diferentes. ¿Te interesa alguno en particular?')

        if precio_promedio > 0:
            sugerencias.append('¿Querés ver opciones en otro rango de precio?')

        # Sugerencia de outfit completo
        if 'outfit' not in query_original.lower() and 'conjunto' not in query_original.lower():
            sugerencias.append('¿Te interesa ver un outfit completo?')

        return sugerencias[:2]  # Máximo 2 sugerencias para no saturar


# Instancia global
_conversacion_service = None

def get_conversacion_service() -> ConversacionService:
    """Singleton del servicio de conversación"""
    global _conversacion_service
    if _conversacion_service is None:
        _conversacion_service = ConversacionService()
    return _conversacion_service
