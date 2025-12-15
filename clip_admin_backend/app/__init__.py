# Flask Admin Backend Package

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from flask import Flask
import os

# Inicializar extensiones
db = SQLAlchemy()
login_manager = LoginManager()
jwt = JWTManager()

# Redis cache (se inicializa en app.py)
redis_cache = None

# Importar modelos para que SQLAlchemy los reconozca
from .models.client import Client
from .models.user import User
from .models.category import Category
from .models.product import Product
from .models.image import Image
from .models.product_attribute_config import ProductAttributeConfig

def create_app():
    app = Flask(__name__)
    # Cargar config desde .env.local si existe
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    return app
