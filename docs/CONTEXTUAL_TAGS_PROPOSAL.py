"""
Tags Contextuales Expandidos para CLIP Comparador V2
Propuesta de mejora para búsquedas conceptuales
"""

# =============================================================================
# TAGS CONTEXTUALES POR OCASIÓN / USO
# =============================================================================

OCCASION_TAGS = [
    # Eventos formales
    "fiesta", "boda", "gala", "ceremonia", "evento_formal",
    
    # Deportes y actividades
    "deporte", "gym", "running", "futbol", "basketball", "ciclismo",
    "yoga", "natacion", "outdoor", "hiking", "camping",
    
    # Trabajo y profesional
    "trabajo", "oficina", "reunion", "presentacion", "profesional",
    "business", "corporativo",
    
    # Casual y diario
    "casual", "diario", "relax", "casa", "salir", "paseo",
    
    # Clima y estaciones
    "verano", "invierno", "lluvia", "frio", "calor", "playa",
    
    # Eventos sociales
    "concierto", "club", "bar", "restaurante", "cita",
]

# =============================================================================
# TAGS FUNCIONALES (QUÉ HACE / PARA QUÉ SIRVE)
# =============================================================================

FUNCTIONAL_TAGS = [
    # Protección
    "protege_sol", "protege_lluvia", "protege_frio", "cubre_cabeza",
    "cubre_bien", "cobertura_total", "transpirable",
    
    # Comodidad
    "comodo", "flexible", "elastico", "ajustable", "holgado",
    "ajustado", "liviano", "pesado",
    
    # Estética
    "elegante", "casual", "deportivo", "moderno", "clasico",
    "vintage", "minimalista", "colorido", "neutro", "brillante",
    
    # Durabilidad
    "resistente", "duradero", "premium", "economico", "basico",
]

# =============================================================================
# TAGS VISUALES ESPECÍFICOS (QUÉ SE VE)
# =============================================================================

VISUAL_TAGS = [
    # Materiales visibles
    "cuero", "tela", "algodon", "sintetico", "mezclilla", "lana",
    "seda", "lino", "nylon", "polyester",
    
    # Patrones y diseños
    "liso", "estampado", "rayas", "cuadros", "floral", "geometrico",
    "bordado", "texturizado",
    
    # Características visuales
    "brillante", "mate", "metalico", "transparente", "opaco",
    "con_logo", "sin_logo", "monocromatico", "multicolor",
    
    # Forma y silueta
    "ajustado", "holgado", "oversize", "slim_fit", "regular_fit",
    "crop", "largo", "corto", "midi",
]

# =============================================================================
# TAGS DEMOGRÁFICOS
# =============================================================================

DEMOGRAPHIC_TAGS = [
    "unisex", "masculino", "femenino", "infantil", "juvenil",
    "adulto", "senior", "plus_size", "petite",
]

# =============================================================================
# CONSOLIDADO: TODOS LOS TAGS CONTEXTUALES
# =============================================================================

CONTEXTUAL_TAG_OPTIONS = (
    OCCASION_TAGS +
    FUNCTIONAL_TAGS +
    VISUAL_TAGS +
    DEMOGRAPHIC_TAGS
)

# Total: ~100+ tags contextuales

# =============================================================================
# PROMPTS CONTEXTUALES PARA CLIP
# =============================================================================

CONTEXTUAL_PROMPTS = {
    # Ocasión
    "fiesta": "elegant party shoes with high heels and shine",
    "deporte": "athletic sportswear for physical activity",
    "futbol": "sporty comfortable clothing for playing soccer",
    "trabajo": "professional business attire for office",
    
    # Funcionalidad
    "cubre_bien": "hat with full head coverage and protection",
    "protege_sol": "sun protection clothing or accessory",
    "comodo": "comfortable loose-fitting casual wear",
    
    # Visual
    "brillante": "shiny glossy material with metallic finish",
    "elegante": "elegant sophisticated formal style",
    "casual": "casual relaxed everyday clothing",
}

# =============================================================================
# MAPEO: QUERY DE USUARIO → TAGS A BUSCAR
# =============================================================================

QUERY_TO_TAGS_MAPPING = {
    # Zapatos de fiesta
    "zapatos fiesta": ["fiesta", "elegante", "brillante", "formal", "femenino"],
    "zapatos evento": ["fiesta", "gala", "elegante", "formal"],
    
    # Gorras deportivas
    "gorra futbol": ["futbol", "deporte", "cubre_bien", "deportivo"],
    "gorra partido": ["deporte", "outdoor", "cubre_cabeza", "casual"],
    
    # Pantalones deportivos
    "pantalon deporte": ["deporte", "comodo", "flexible", "deportivo"],
    "pantalon futbol": ["futbol", "deporte", "elastico", "comodo"],
    
    # Trabajo
    "camisa trabajo": ["trabajo", "profesional", "formal", "oficina"],
    "zapatos oficina": ["trabajo", "profesional", "elegante", "formal"],
}

# =============================================================================
# EJEMPLO DE USO
# =============================================================================

"""
Query del usuario: "Quiero zapatos para una fiesta"

1. Detección de intención:
   - Producto: "zapatos"
   - Ocasión: "fiesta"
   
2. Tags contextuales a inferir:
   ["fiesta", "elegante", "brillante", "formal", "femenino"]
   
3. Prompts CLIP generados:
   - "elegant party shoes with high heels and shine"
   - "formal elegant footwear for events"
   - "shiny glossy shoes for celebration"
   
4. Búsqueda:
   - Embedding del query enriquecido con prompts contextuales
   - Comparar contra productos que tengan tags: fiesta, elegante, brillante
   - Boost adicional si el producto tiene esos tags en su metadata
"""

# =============================================================================
# INTEGRACIÓN CON ATTRIBUTE AUTOFILL SERVICE
# =============================================================================

"""
Modificar AttributeAutofillService para:

1. Usar CONTEXTUAL_TAG_OPTIONS en lugar de TAG_OPTIONS básico
2. Aplicar threshold más bajo (0.20) para capturar más contextos
3. Almacenar top 5-10 tags en campo Product.tags
4. Agregar campo Product.contextual_metadata (JSON) con:
   {
     "occasion": ["fiesta", "gala"],
     "functional": ["comodo", "elegante"],
     "visual": ["brillante", "ajustado"],
     "demographic": ["femenino"]
   }
"""
