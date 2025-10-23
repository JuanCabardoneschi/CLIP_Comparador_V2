"""
Templates de atributos por industria para SearchOptimizer

Estos templates definen los atributos del sistema que se crean automáticamente
cuando se registra un nuevo cliente, según su industria.

Los atributos marcados con is_system=True:
- NO pueden ser eliminados por el usuario
- SÍ pueden ser editados (ej: agregar más opciones a listas)
- Son usados por SearchOptimizer para metadata scoring
- Tienen un optimizer_weight que indica su importancia

Uso:
    from app.utils.industry_templates import get_industry_template
    template = get_industry_template('fashion')
"""

INDUSTRY_TEMPLATES = {
    'fashion': {
        'color': {
            'label': 'Color',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Color principal del producto. Usado por el buscador visual para mejorar coincidencias de color.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'marca': {
            'label': 'Marca',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Marca o fabricante del producto. Ayuda a encontrar productos de la misma marca.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'material': {
            'label': 'Material',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.7,
            'description': 'Material de fabricación principal. Permite búsquedas por composición.',
            'options': {
                'multiple': False,
                'values': ['Algodón', 'Cuero', 'Poliéster', 'Lino', 'Seda', 'Lana', 'Sintético', 'Mezclilla', 'Nylon']
            },
            'expose_in_search': True,
            'required': False
        },
        'talla': {
            'label': 'Talla',
            'type': 'list',
            'is_system': False,  # No usado en optimizer
            'is_deletable': True,
            'optimizer_weight': None,
            'description': 'Tallas disponibles del producto.',
            'options': {
                'multiple': True,
                'values': ['XS', 'S', 'M', 'L', 'XL', 'XXL']
            },
            'expose_in_search': True,
            'required': False
        }
    },

    'automotive': {
        'color': {
            'label': 'Color',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.6,
            'description': 'Color del repuesto. Útil para piezas visibles como paragolpes, espejos, etc.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'marca': {
            'label': 'Marca Compatible',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Marca(s) de vehículo con las que es compatible este repuesto.',
            'options': {
                'multiple': True,
                'values': ['Toyota', 'Ford', 'Chevrolet', 'Honda', 'Volkswagen', 'Nissan', 'Hyundai', 'Kia', 'Renault', 'Peugeot', 'Fiat']
            },
            'expose_in_search': True,
            'required': False
        },
        'modelo': {
            'label': 'Modelo Compatible',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Modelo de vehículo compatible (ej: Corolla 2020, Focus 2018-2022).',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'material': {
            'label': 'Tipo de Repuesto',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.5,
            'description': 'Calidad del repuesto.',
            'options': {
                'multiple': False,
                'values': ['Original', 'Genérico OEM', 'Aftermarket Premium', 'Genérico Standard']
            },
            'expose_in_search': True,
            'required': False
        },
        'categoria': {
            'label': 'Categoría de Repuesto',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.9,
            'description': 'Categoría del sistema del vehículo.',
            'options': {
                'multiple': False,
                'values': ['Frenos', 'Motor', 'Suspensión', 'Eléctrico', 'Carrocería', 'Transmisión', 'Dirección', 'Refrigeración', 'Escape']
            },
            'expose_in_search': True,
            'required': False
        }
    },

    'home': {
        'color': {
            'label': 'Color',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Color principal del artículo.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'marca': {
            'label': 'Marca',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.8,
            'description': 'Marca del producto de hogar.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'material': {
            'label': 'Material',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.7,
            'description': 'Material principal de fabricación.',
            'options': {
                'multiple': False,
                'values': ['Plástico', 'Vidrio', 'Cerámica', 'Madera', 'Metal', 'Tela', 'Bambú', 'Silicona', 'Acero Inoxidable']
            },
            'expose_in_search': True,
            'required': False
        },
        'ambiente': {
            'label': 'Ambiente',
            'type': 'list',
            'is_system': False,
            'is_deletable': True,
            'optimizer_weight': None,
            'description': 'Ambiente(s) donde se usa el producto.',
            'options': {
                'multiple': True,
                'values': ['Cocina', 'Baño', 'Dormitorio', 'Living', 'Comedor', 'Jardín', 'Exterior', 'Lavadero']
            },
            'expose_in_search': True,
            'required': False
        },
        'estilo': {
            'label': 'Estilo',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.6,
            'description': 'Estilo decorativo del artículo.',
            'options': {
                'multiple': False,
                'values': ['Moderno', 'Clásico', 'Minimalista', 'Rústico', 'Industrial', 'Vintage', 'Escandinavo', 'Contemporáneo']
            },
            'expose_in_search': True,
            'required': False
        }
    },

    'electronics': {
        'marca': {
            'label': 'Marca',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 1.0,
            'description': 'Marca del dispositivo electrónico.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'modelo': {
            'label': 'Modelo',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.9,
            'description': 'Modelo específico del producto (ej: iPhone 15 Pro, Galaxy S24).',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'color': {
            'label': 'Color',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.5,
            'description': 'Color del dispositivo (menos relevante en electrónica).',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'categoria': {
            'label': 'Categoría',
            'type': 'list',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.8,
            'description': 'Categoría del dispositivo electrónico.',
            'options': {
                'multiple': False,
                'values': ['Smartphones', 'Laptops', 'Tablets', 'Audio', 'Gaming', 'Smartwatches', 'Accesorios', 'TV', 'Cámaras']
            },
            'expose_in_search': True,
            'required': False
        }
    },

    'generic': {
        'marca': {
            'label': 'Marca',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.9,
            'description': 'Marca del producto.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'color': {
            'label': 'Color',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.8,
            'description': 'Color principal del producto.',
            'options': None,
            'expose_in_search': True,
            'required': False
        },
        'material': {
            'label': 'Material',
            'type': 'text',
            'is_system': True,
            'is_deletable': False,
            'optimizer_weight': 0.6,
            'description': 'Material de fabricación.',
            'options': None,
            'expose_in_search': True,
            'required': False
        }
    }
}


def get_industry_template(industry: str) -> dict:
    """
    Obtener template de atributos para una industria.

    Args:
        industry: Código de industria ('fashion', 'automotive', etc.)

    Returns:
        Dict con atributos del template. Si no existe, retorna 'generic'

    Example:
        >>> template = get_industry_template('fashion')
        >>> for key, config in template.items():
        ...     print(f"{key}: {config['label']}")
    """
    return INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES['generic'])


def get_available_industries() -> list:
    """
    Listar industrias disponibles con templates

    Returns:
        Lista de tuplas (código, nombre_display)
    """
    return [
        ('fashion', 'Moda y Textil'),
        ('automotive', 'Repuestos de Auto'),
        ('home', 'Hogar y Bazar'),
        ('electronics', 'Electrónica'),
        ('generic', 'Genérico')
    ]


def get_system_attributes_for_industry(industry: str) -> list:
    """
    Obtener solo los atributos del sistema (usados en optimizer) para una industria

    Args:
        industry: Código de industria

    Returns:
        Lista de tuplas (key, label, weight)
    """
    template = get_industry_template(industry)
    return [
        (key, config['label'], config['optimizer_weight'])
        for key, config in template.items()
        if config['is_system'] and config['optimizer_weight'] is not None
    ]
