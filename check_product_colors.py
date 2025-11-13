#!/usr/bin/env python3
"""
Verificar qué productos de Goody tienen atributos de color
"""

import sys
import os

backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clip_admin_backend')
sys.path.insert(0, backend_path)
os.chdir(backend_path)

from app import db
from app.models import Client, Product
from flask import Flask

def check_colors():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Laurana%4001@localhost:5432/clip_comparador_v2'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        goody = Client.query.filter_by(name='Goody Store').first()
        products = Product.query.filter_by(client_id=goody.id).all()

        print(f"📦 Total productos: {len(products)}\n")

        with_color = 0
        without_color = 0

        for p in products:
            if p.attributes and isinstance(p.attributes, dict):
                color = p.attributes.get('color')
                if color:
                    print(f"✅ {p.name}: {color}")
                    with_color += 1
                else:
                    print(f"❌ {p.name}: SIN COLOR")
                    without_color += 1
            else:
                print(f"⚠️  {p.name}: Sin attributes")
                without_color += 1

        print(f"\n📊 Resumen:")
        print(f"   Con color: {with_color}")
        print(f"   Sin color: {without_color}")

if __name__ == "__main__":
    check_colors()
