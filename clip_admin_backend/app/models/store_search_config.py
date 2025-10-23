"""
Modelo StoreSearchConfig para CLIP Comparador V2
Configuración de optimizadores de búsqueda por tienda
"""
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from . import db


class StoreSearchConfig(db.Model):
    """
    Configuración de pesos para el motor de búsqueda optimizado por tienda.

    Permite a cada tienda configurar la importancia relativa de 3 capas de scoring:
    - Visual Layer: Similitud CLIP + boosts (color, categoría)
    - Metadata Layer: Coincidencias exactas de atributos
    - Business Layer: Lógica de negocio (stock, featured, etc.)

    La suma de los 3 pesos debe ser 1.0 (±0.01 de tolerancia).

    Ejemplo:
        config = StoreSearchConfig(
            store_id='uuid-abc-123',
            visual_weight=0.6,
            metadata_weight=0.3,
            business_weight=0.1
        )

        # Validar pesos
        is_valid, error = config.validate_weights()
        if not is_valid:
            raise ValueError(error)
    """
    __tablename__ = 'store_search_config'

    # Clave primaria: ID de la tienda (FK a clients) - UUID nativo
    store_id = db.Column(
        db.dialects.postgresql.UUID(as_uuid=False),  # Guardado como string pero compatible con UUID
        db.ForeignKey('clients.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False
    )    # ===================================================================
    # PESOS DE LAS 3 CAPAS (deben sumar 1.0)
    # ===================================================================

    visual_weight = db.Column(
        db.Float,
        nullable=False,
        default=0.6,
        comment='Peso de similitud visual CLIP (0.0-1.0)'
    )

    metadata_weight = db.Column(
        db.Float,
        nullable=False,
        default=0.3,
        comment='Peso de coincidencias de metadatos (0.0-1.0)'
    )

    business_weight = db.Column(
        db.Float,
        nullable=False,
        default=0.1,
        comment='Peso de lógica de negocio (0.0-1.0)'
    )

    # ===================================================================
    # CONFIGURACIÓN DE METADATOS (JSONB)
    # ===================================================================

    metadata_config = db.Column(
        db.JSON,
        nullable=False,
        default={
            'color': {'enabled': True, 'weight': 0.3},
            'brand': {'enabled': True, 'weight': 0.3},
            'pattern': {'enabled': False, 'weight': 0.2}
        },
        comment='Configuración de atributos de metadata y sus pesos'
    )

    # ===================================================================
    # METADATOS DEL MODELO
    # ===================================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # ===================================================================
    # RELACIONES
    # ===================================================================

    # Relación con Client (many-to-one, aunque es 1-to-1 por el PK)
    store = db.relationship(
        'Client',
        backref=db.backref('search_config', uselist=False, cascade='all, delete-orphan')
    )

    def __init__(self, **kwargs):
        """
        Constructor del modelo.

        Args:
            store_id (str): ID del cliente/tienda
            visual_weight (float): Peso visual (default 0.6)
            metadata_weight (float): Peso metadata (default 0.3)
            business_weight (float): Peso business (default 0.1)
            metadata_config (dict): Config de atributos de metadata
        """
        # Asegurar valores default si no se proporcionan
        if 'visual_weight' not in kwargs:
            kwargs['visual_weight'] = 0.6
        if 'metadata_weight' not in kwargs:
            kwargs['metadata_weight'] = 0.3
        if 'business_weight' not in kwargs:
            kwargs['business_weight'] = 0.1
        if 'metadata_config' not in kwargs:
            kwargs['metadata_config'] = {
                'color': {'enabled': True, 'weight': 0.3},
                'brand': {'enabled': True, 'weight': 0.3},
                'pattern': {'enabled': False, 'weight': 0.2}
            }
        
        super(StoreSearchConfig, self).__init__(**kwargs)

    def __repr__(self):
        return (
            f'<StoreSearchConfig store_id={self.store_id} '
            f'weights=({self.visual_weight}, {self.metadata_weight}, {self.business_weight})>'
        )

    # ===================================================================
    # MÉTODOS DE VALIDACIÓN
    # ===================================================================

    def validate_weights(self) -> Tuple[bool, Optional[str]]:
        """
        Valida que los pesos sean correctos.

        Reglas:
        - Cada peso debe estar entre 0.0 y 1.0
        - La suma de los 3 pesos debe ser 1.0 (±0.01 de tolerancia)

        Returns:
            Tuple[bool, Optional[str]]: (es_válido, mensaje_de_error)

        Example:
            >>> config = StoreSearchConfig(store_id='123', visual_weight=0.5,
            ...                            metadata_weight=0.3, business_weight=0.2)
            >>> is_valid, error = config.validate_weights()
            >>> print(is_valid)
            True

            >>> config2 = StoreSearchConfig(store_id='123', visual_weight=1.5,
            ...                             metadata_weight=0.3, business_weight=0.2)
            >>> is_valid, error = config2.validate_weights()
            >>> print(error)
            'visual_weight must be between 0.0 and 1.0'
        """
        # Validar rangos individuales
        if not 0.0 <= self.visual_weight <= 1.0:
            return False, 'visual_weight must be between 0.0 and 1.0'

        if not 0.0 <= self.metadata_weight <= 1.0:
            return False, 'metadata_weight must be between 0.0 and 1.0'

        if not 0.0 <= self.business_weight <= 1.0:
            return False, 'business_weight must be between 0.0 and 1.0'

        # Validar suma total (con tolerancia de 0.01)
        total = self.visual_weight + self.metadata_weight + self.business_weight
        if abs(total - 1.0) > 0.01:
            return False, f'Sum of weights must be 1.0 (±0.01), got {total:.3f}'

        return True, None

    def validate_metadata_config(self) -> Tuple[bool, Optional[str]]:
        """
        Valida la configuración de metadatos.

        Reglas:
        - metadata_config debe ser un dict
        - Cada atributo debe tener 'enabled' (bool) y 'weight' (float)
        - Los pesos de metadata deben estar entre 0.0 y 1.0

        Returns:
            Tuple[bool, Optional[str]]: (es_válido, mensaje_de_error)
        """
        if not isinstance(self.metadata_config, dict):
            return False, 'metadata_config must be a dictionary'

        for attr_name, attr_config in self.metadata_config.items():
            if not isinstance(attr_config, dict):
                return False, f'{attr_name} config must be a dictionary'

            if 'enabled' not in attr_config:
                return False, f'{attr_name} must have "enabled" field'

            if 'weight' not in attr_config:
                return False, f'{attr_name} must have "weight" field'

            if not isinstance(attr_config['enabled'], bool):
                return False, f'{attr_name}.enabled must be a boolean'

            weight = attr_config['weight']
            if not isinstance(weight, (int, float)) or not 0.0 <= weight <= 1.0:
                return False, f'{attr_name}.weight must be between 0.0 and 1.0'

        return True, None

    # ===================================================================
    # MÉTODOS HELPER
    # ===================================================================

    @staticmethod
    def get_or_create_default(store_id: str, commit: bool = False) -> 'StoreSearchConfig':
        """
        Obtiene la configuración de una tienda o crea una con valores default.

        Args:
            store_id (str): ID de la tienda
            commit (bool): Si True, guarda en BD inmediatamente

        Returns:
            StoreSearchConfig: Configuración existente o nueva

        Example:
            >>> config = StoreSearchConfig.get_or_create_default('uuid-123', commit=True)
            >>> print(config.visual_weight)
            0.6
        """
        config = StoreSearchConfig.query.get(store_id)

        if config is None:
            config = StoreSearchConfig(
                store_id=store_id,
                visual_weight=0.6,
                metadata_weight=0.3,
                business_weight=0.1,
                metadata_config={
                    'color': {'enabled': True, 'weight': 0.3},
                    'brand': {'enabled': True, 'weight': 0.3},
                    'pattern': {'enabled': False, 'weight': 0.2}
                }
            )

            if commit:
                db.session.add(config)
                db.session.commit()

        return config

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el modelo a diccionario para serialización JSON.

        Returns:
            Dict[str, Any]: Representación en dict del modelo
        """
        return {
            'store_id': self.store_id,
            'visual_weight': self.visual_weight,
            'metadata_weight': self.metadata_weight,
            'business_weight': self.business_weight,
            'metadata_config': self.metadata_config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def apply_preset(self, preset_name: str) -> None:
        """
        Aplica un preset de configuración predefinido.

        Presets disponibles:
        - 'visual': Prioriza similitud visual (0.8, 0.1, 0.1)
        - 'metadata': Prioriza exactitud de atributos (0.3, 0.6, 0.1)
        - 'balanced': Configuración balanceada (0.6, 0.3, 0.1)

        Args:
            preset_name (str): Nombre del preset

        Raises:
            ValueError: Si el preset no existe

        Example:
            >>> config = StoreSearchConfig(store_id='123')
            >>> config.apply_preset('visual')
            >>> print(config.visual_weight)
            0.8
        """
        presets = {
            'visual': (0.8, 0.1, 0.1),
            'metadata': (0.3, 0.6, 0.1),
            'balanced': (0.6, 0.3, 0.1)
        }

        if preset_name not in presets:
            raise ValueError(
                f'Unknown preset: {preset_name}. '
                f'Available: {", ".join(presets.keys())}'
            )

        visual, metadata, business = presets[preset_name]
        self.visual_weight = visual
        self.metadata_weight = metadata
        self.business_weight = business

    def get_enabled_metadata_attributes(self) -> list[str]:
        """
        Obtiene lista de atributos de metadata habilitados.

        Returns:
            list[str]: Lista de nombres de atributos habilitados

        Example:
            >>> config = StoreSearchConfig(store_id='123')
            >>> enabled = config.get_enabled_metadata_attributes()
            >>> print(enabled)
            ['color', 'brand']
        """
        return [
            attr_name
            for attr_name, attr_config in self.metadata_config.items()
            if attr_config.get('enabled', False)
        ]

    def update_weights(
        self,
        visual: Optional[float] = None,
        metadata: Optional[float] = None,
        business: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Actualiza los pesos y valida automáticamente.

        Args:
            visual (float, optional): Nuevo peso visual
            metadata (float, optional): Nuevo peso metadata
            business (float, optional): Nuevo peso business

        Returns:
            Tuple[bool, Optional[str]]: (éxito, mensaje_de_error)

        Example:
            >>> config = StoreSearchConfig(store_id='123')
            >>> success, error = config.update_weights(visual=0.7, metadata=0.2)
            >>> if not success:
            ...     print(error)
        """
        # Actualizar solo los pesos proporcionados
        if visual is not None:
            self.visual_weight = visual
        if metadata is not None:
            self.metadata_weight = metadata
        if business is not None:
            self.business_weight = business

        # Validar
        return self.validate_weights()
