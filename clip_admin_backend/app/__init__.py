# Flask Admin Backend Package

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

# Inicializar extensiones
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
jwt = JWTManager()

# Importar modelos para que SQLAlchemy los reconozca
from .models.client import Client
from .models.user import User
from .models.category import Category
from .models.product import Product
from .models.image import Image
from .models.product_attribute_config import ProductAttributeConfig
