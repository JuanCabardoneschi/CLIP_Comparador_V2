# Modelos SQLAlchemy
# Importar db desde el módulo principal de la app
from .. import db

# Importar modelos básicos
from .client import Client
from .user import User
from .category import Category
from .product import Product
from .image import Image
from .search_log import SearchLog
