#!/usr/bin/env python3
"""
DB Utils - Utilidades para la base de datos
Script para consultas rápidas y manipulación de datos
"""

import sys
import os

# Agregar el directorio del backend al path
backend_path = os.path.join(os.path.dirname(__file__), 'clip_admin_backend')
sys.path.insert(0, backend_path)

# Cambiar al directorio del backend para que Flask encuentre los archivos
os.chdir(backend_path)

# Ahora importar lo que necesitamos
exec(open('app.py').read())  # Esto carga la app de la misma forma que app.py
from app.models.user import User
from app.models.client import Client
from app.models.product import Product
from app.models.category import Category
from app.models.image import Image
from app.models.search_log import SearchLog

def show_users():
    """Mostrar todos los usuarios"""
    with app.app_context():
        users = User.query.all()
        print(f"\n📋 USUARIOS ({len(users)} total):")
        print("-" * 80)
        for user in users:
            client_name = user.client.name if user.client else "Sin cliente"
            print(f"📧 {user.email:<25} | 👤 {user.role:<12} | 🏢 {client_name}")

def show_clients():
    """Mostrar todos los clientes"""
    with app.app_context():
        clients = Client.query.all()
        print(f"\n🏢 CLIENTES ({len(clients)} total):")
        print("-" * 80)
        for client in clients:
            products_count = Product.query.filter_by(client_id=client.id).count()
            images_count = Image.query.filter_by(client_id=client.id).count()
            print(f"🏢 {client.name:<25} | 📦 {products_count} productos | 🖼️  {images_count} imágenes")

def show_products(client_email=None):
    """Mostrar productos (opcionalmente de un cliente específico)"""
    with app.app_context():
        if client_email:
            user = User.query.filter_by(email=client_email).first()
            if not user or not user.client_id:
                print(f"❌ Usuario {client_email} no encontrado o sin cliente")
                return
            products = Product.query.filter_by(client_id=user.client_id).all()
            print(f"\n📦 PRODUCTOS DE {user.client.name} ({len(products)} total):")
        else:
            products = Product.query.all()
            print(f"\n📦 TODOS LOS PRODUCTOS ({len(products)} total):")

        print("-" * 100)
        for product in products:
            client_name = product.client.name if product.client else "Sin cliente"
            active = "✅" if product.is_active else "❌"
            print(f"{active} {product.name:<30} | SKU: {product.sku:<15} | 💰 ${product.price} | 🏢 {client_name}")

def show_images(client_email=None):
    """Mostrar imágenes (opcionalmente de un cliente específico)"""
    with app.app_context():
        if client_email:
            user = User.query.filter_by(email=client_email).first()
            if not user or not user.client_id:
                print(f"❌ Usuario {client_email} no encontrado o sin cliente")
                return
            images = Image.query.filter_by(client_id=user.client_id).all()
            print(f"\n🖼️  IMÁGENES DE {user.client.name} ({len(images)} total):")
        else:
            images = Image.query.all()
            print(f"\n🖼️  TODAS LAS IMÁGENES ({len(images)} total):")

        print("-" * 100)
        for img in images:
            processed = "✅" if img.is_processed else "⏳"
            client_name = img.client.name if img.client else "Sin cliente"
            print(f"{processed} {img.filename:<30} | 📁 {img.upload_status:<10} | 🏢 {client_name}")

def create_demo_products(client_email="admin@demo.com"):
    """Crear productos de demostración"""
    with app.app_context():
        user = User.query.filter_by(email=client_email).first()
        if not user or not user.client_id:
            print(f"❌ Usuario {client_email} no encontrado o sin cliente")
            return

        # Crear categoría
        category = Category.query.filter_by(client_id=user.client_id, name='Camisetas').first()
        if not category:
            category = Category(
                client_id=user.client_id,
                name='Camisetas',
                description='Camisetas y polos'
            )
            db.session.add(category)
            db.session.commit()
            print('✅ Categoría "Camisetas" creada')

        # Productos demo
        productos_demo = [
            {'name': 'Camiseta Azul Básica', 'sku': 'CAM-AZ-001', 'price': 25.99},
            {'name': 'Polo Negro Deportivo', 'sku': 'POL-NE-001', 'price': 35.50},
            {'name': 'Camiseta Blanca Algodón', 'sku': 'CAM-BL-001', 'price': 22.99},
            {'name': 'Polo Gris Casual', 'sku': 'POL-GR-001', 'price': 28.75},
            {'name': 'Camiseta Verde Estampada', 'sku': 'CAM-VE-001', 'price': 30.00}
        ]

        productos_creados = 0
        for producto_data in productos_demo:
            existing = Product.query.filter_by(client_id=user.client_id, sku=producto_data['sku']).first()
            if not existing:
                producto = Product(
                    client_id=user.client_id,
                    category_id=category.id,
                    name=producto_data['name'],
                    sku=producto_data['sku'],
                    price=producto_data['price'],
                    description=f"Producto demo: {producto_data['name']}",
                    stock=50,
                    is_active=True
                )
                db.session.add(producto)
                productos_creados += 1

        db.session.commit()
        print(f'✅ {productos_creados} productos creados para {user.client.name}')

def show_stats():
    """Mostrar estadísticas generales"""
    with app.app_context():
        print("\n📊 ESTADÍSTICAS GENERALES:")
        print("-" * 50)
        print(f"👤 Usuarios:     {User.query.count()}")
        print(f"🏢 Clientes:     {Client.query.count()}")
        print(f"📦 Productos:    {Product.query.count()}")
        print(f"🖼️  Imágenes:     {Image.query.count()}")
        print(f"✅ Procesadas:   {Image.query.filter_by(is_processed=True).count()}")
        print(f"🔍 Búsquedas:    {SearchLog.query.count()}")

def interactive_menu():
    """Menú interactivo"""
    while True:
        print("\n" + "="*60)
        print("🗄️  CLIP DB UTILS - Menú Principal")
        print("="*60)
        print("1. 👤 Mostrar usuarios")
        print("2. 🏢 Mostrar clientes")
        print("3. 📦 Mostrar todos los productos")
        print("4. 📦 Mostrar productos de un cliente")
        print("5. 🖼️  Mostrar todas las imágenes")
        print("6. 🖼️  Mostrar imágenes de un cliente")
        print("7. 🎯 Crear productos demo")
        print("8. 📊 Mostrar estadísticas")
        print("0. ❌ Salir")
        print("-" * 60)

        choice = input("Selecciona una opción: ").strip()

        if choice == "1":
            show_users()
        elif choice == "2":
            show_clients()
        elif choice == "3":
            show_products()
        elif choice == "4":
            email = input("Email del cliente: ").strip()
            show_products(email)
        elif choice == "5":
            show_images()
        elif choice == "6":
            email = input("Email del cliente: ").strip()
            show_images(email)
        elif choice == "7":
            email = input("Email del cliente (default: admin@demo.com): ").strip()
            if not email:
                email = "admin@demo.com"
            create_demo_products(email)
        elif choice == "8":
            show_stats()
        elif choice == "0":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción no válida")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "users":
            show_users()
        elif command == "clients":
            show_clients()
        elif command == "products":
            show_products()
        elif command == "images":
            show_images()
        elif command == "demo":
            create_demo_products()
        elif command == "stats":
            show_stats()
        else:
            print(f"❌ Comando '{command}' no reconocido")
            print("Comandos disponibles: users, clients, products, images, demo, stats")
    else:
        interactive_menu()
