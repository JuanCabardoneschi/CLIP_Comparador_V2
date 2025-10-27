"""
Sistema de configuración basado en archivo JSON
Permite al SuperAdmin editar configuraciones sin acceder a variables de entorno
"""

import json
import os
from typing import Any, Dict


class SystemConfigManager:
    """Gestor de configuración del sistema desde JSON"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    @property
    def config_path(self) -> str:
        """Ruta al archivo de configuración"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'config', 'system_config.json')
    
    def load_config(self) -> Dict[str, Any]:
        """Cargar configuración desde JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
                print(f"✅ Configuración del sistema cargada desde {self.config_path}")
                return self._config
        except FileNotFoundError:
            print(f"⚠️  Archivo de configuración no encontrado: {self.config_path}")
            self._config = self._get_default_config()
            self.save_config()
            return self._config
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON de configuración: {e}")
            self._config = self._get_default_config()
            return self._config
    
    def save_config(self) -> bool:
        """Guardar configuración a JSON"""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            print(f"✅ Configuración guardada en {self.config_path}")
            return True
        except Exception as e:
            print(f"❌ Error guardando configuración: {e}")
            return False
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Obtener valor de configuración
        
        Args:
            section: Sección de configuración ('clip', 'search', 'system')
            key: Clave dentro de la sección
            default: Valor por defecto si no existe
            
        Returns:
            Valor de configuración o default
        """
        if self._config is None:
            self.load_config()
        
        return self._config.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """
        Establecer valor de configuración
        
        Args:
            section: Sección de configuración
            key: Clave dentro de la sección
            value: Nuevo valor
            
        Returns:
            True si se guardó correctamente
        """
        if self._config is None:
            self.load_config()
        
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section][key] = value
        return self.save_config()
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Obtener sección completa de configuración"""
        if self._config is None:
            self.load_config()
        
        return self._config.get(section, {})
    
    def update_section(self, section: str, values: Dict[str, Any]) -> bool:
        """
        Actualizar múltiples valores de una sección
        
        Args:
            section: Sección a actualizar
            values: Diccionario con nuevos valores
            
        Returns:
            True si se guardó correctamente
        """
        if self._config is None:
            self.load_config()
        
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section].update(values)
        return self.save_config()
    
    def reload(self) -> Dict[str, Any]:
        """Recargar configuración desde disco"""
        return self.load_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Configuración por defecto"""
        return {
            "clip": {
                "idle_timeout": 1800,
                "preload": False,
                "description": "Configuración del modelo CLIP para búsqueda visual"
            },
            "search": {
                "max_results": 10,
                "default_threshold": 0.1,
                "description": "Configuración por defecto para búsquedas visuales"
            },
            "system": {
                "session_timeout": 7200,
                "max_upload_size_mb": 50,
                "description": "Configuración general del sistema"
            }
        }
    
    def get_all(self) -> Dict[str, Any]:
        """Obtener toda la configuración"""
        if self._config is None:
            self.load_config()
        return self._config


# Instancia singleton
system_config = SystemConfigManager()
