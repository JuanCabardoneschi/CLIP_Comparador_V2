#!/usr/bin/env python3
"""
DB Utils - Utilidades simples para la base de datos
"""

def create_demo_products():
    """Crear productos de demostración para el Store Admin"""
    import sys, os
    sys.path.insert(0, 'clip_admin_backend')
    os.chdir('clip_admin_backend')

    exec(open('app.py').read())
    from app.models.user import User
    from app.models.product import Product
    from app.models.category import Category

    with app.app_context():
        # Buscar el usuario Store Admin
        store_admin = User.query.filter_by(email='admin@demo.com').first()
        if not store_admin:
            print('❌ Usuario Store Admin no encontrado')
            return

        print(f'✅ Store Admin encontrado: {store_admin.email} - Cliente: {store_admin.client_id}')

        # Crear categoría si no existe
        category = Category.query.filter_by(client_id=store_admin.client_id, name='Camisetas').first()
        if not category:
            category = Category(
                client_id=store_admin.client_id,
                name='Camisetas',
                description='Camisetas y polos'
            )
            db.session.add(category)
            db.session.commit()
            print('✅ Categoría "Camisetas" creada')
        else:
            print('✅ Categoría "Camisetas" ya existe')

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
            existing = Product.query.filter_by(client_id=store_admin.client_id, sku=producto_data['sku']).first()
            if not existing:
                producto = Product(
                    client_id=store_admin.client_id,
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

        # Verificar totales
        total_productos = Product.query.filter_by(client_id=store_admin.client_id).count()
        print(f'✅ Productos creados: {productos_creados}')
        print(f'✅ Total productos del cliente: {total_productos}')

def show_stats():
    """Mostrar estadísticas de la base de datos"""
    import sys, os
    sys.path.insert(0, 'clip_admin_backend')
    os.chdir('clip_admin_backend')

    exec(open('app.py').read())
    from app.models.user import User
    from app.models.client import Client
    from app.models.product import Product
    from app.models.image import Image

    with app.app_context():
        print("\n📊 ESTADÍSTICAS DE LA BASE DE DATOS:")
        print("-" * 50)
        print(f"👤 Usuarios:     {User.query.count()}")
        print(f"🏢 Clientes:     {Client.query.count()}")
        print(f"📦 Productos:    {Product.query.count()}")
        print(f"🖼️  Imágenes:     {Image.query.count()}")
        print(f"✅ Procesadas:   {Image.query.filter_by(is_processed=True).count()}")

        # Mostrar por cliente
        print("\n📊 POR CLIENTE:")
        print("-" * 50)
        clients = Client.query.all()
        for client in clients:
            products_count = Product.query.filter_by(client_id=client.id).count()
            images_count = Image.query.filter_by(client_id=client.id).count()
            print(f"🏢 {client.name}: 📦 {products_count} productos, 🖼️ {images_count} imágenes")

def show_users():
    """Mostrar usuarios"""
    import sys, os
    sys.path.insert(0, 'clip_admin_backend')
    os.chdir('clip_admin_backend')

    exec(open('app.py').read())
    from app.models.user import User

    with app.app_context():
        users = User.query.all()
        print(f"\n👤 USUARIOS ({len(users)} total):")
        print("-" * 80)
        for user in users:
            client_name = user.client.name if user.client else "Sin cliente"
            print(f"📧 {user.email:<25} | 👤 {user.role:<12} | 🏢 {client_name}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "demo":
            create_demo_products()
        elif command == "stats":
            show_stats()
        elif command == "users":
            show_users()
        else:
            print(f"❌ Comando '{command}' no reconocido")
            print("Comandos disponibles: demo, stats, users")
    else:
        print("📋 Comandos disponibles:")
        print("  python db_helper.py demo   - Crear productos demo")
        print("  python db_helper.py stats  - Mostrar estadísticas")
        print("  python db_helper.py users  - Mostrar usuarios")
