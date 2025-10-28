"""
Gestión de configuración del sistema desde archivo JSON
Permite configurar parámetros globales sin reiniciar la aplicación
"""

import os
import json
import threading
from pathlib import Path
from typing import Any, Optional


class SystemConfig:
    """Gestor de configuración del sistema con lectura/escritura thread-safe"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Inicializar gestor de configuración

        Args:
            config_path: Ruta al archivo JSON. Si es None, usa ubicación por defecto.
        """
        if config_path is None:
            # Ubicación por defecto: raíz del proyecto
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            config_path = base_dir / 'system_config.json'

        self.config_path = Path(config_path)
        self._lock = threading.Lock()
        self._config_cache = None
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Crear archivo de configuración con valores por defecto si no existe"""
        if not self.config_path.exists():
            default_config = {
                "clip": {
                    "preload": False,
                    "idle_timeout_minutes": 30,
                    "model_name": "openai/clip-vit-base-patch16"
                },
                "search": {
                    "max_results": 3,
                    "enable_category_detection": True,
                    "enable_visual_search": True
                },
                "system": {
                    "environment": "production",
                    "version": "2.0.0"
                }
            }
            self._write_config(default_config)
            import logging
            logging.getLogger("system_config").info(f"✅ Configuración del sistema creada en: {self.config_path}")

    def _read_config(self) -> dict:
        """Leer configuración desde archivo JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            import logging
            logging.getLogger("system_config").error(f"❌ Error leyendo configuración: {e}")
            return {}

    def _write_config(self, config: dict):
        """Escribir configuración a archivo JSON"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            # Invalidar caché
            self._config_cache = None
        except Exception as e:
            import logging
            logging.getLogger("system_config").error(f"❌ Error escribiendo configuración: {e}")
            raise

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Obtener valor de configuración

        Args:
            section: Sección de configuración (ej: 'clip', 'search')
            key: Clave dentro de la sección
            default: Valor por defecto si no existe (NO USAR para valores críticos)

        Returns:
            Valor configurado

        Raises:
            KeyError: Si el valor no existe en la configuración
        """
        with self._lock:
            config = self._read_config()
            if section not in config or key not in config[section]:
                raise KeyError(f"Config value missing: [{section}][{key}]")
            return config[section][key]

    def set(self, section: str, key: str, value: Any):
        """
        Establecer valor de configuración

        Args:
            section: Sección de configuración
            key: Clave dentro de la sección
            value: Nuevo valor
        """
        with self._lock:
            config = self._read_config()
            if section not in config:
                config[section] = {}
            config[section][key] = value
            self._write_config(config)

    def get_section(self, section: str) -> dict:
        """
        Obtener toda una sección de configuración

        Args:
            section: Nombre de la sección

        Returns:
            Diccionario con toda la sección
        """
        with self._lock:
            config = self._read_config()
            return config.get(section, {})

    def set_section(self, section: str, values: dict):
        """
        Establecer toda una sección de configuración

        Args:
            section: Nombre de la sección
            values: Diccionario con nuevos valores
        """
        with self._lock:
            config = self._read_config()
            config[section] = values
            self._write_config(config)

    def get_all(self) -> dict:
        """Obtener toda la configuración"""
        with self._lock:
            return self._read_config()

    def update_multiple(self, updates: dict):
        """
        Actualizar múltiples valores

        Args:
            updates: Diccionario con estructura {section: {key: value}}
        """
        with self._lock:
            config = self._read_config()
            for section, values in updates.items():
                if section not in config:
                    config[section] = {}
                config[section].update(values)
            self._write_config(config)


# Instancia global del gestor de configuración
system_config = SystemConfig()
