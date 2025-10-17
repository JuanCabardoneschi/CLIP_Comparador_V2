"""
Script para insertar configuraciones de atributos de ejemplo
Ejecutar después de tener un cliente en la base de datos
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar variables de entorno
load_dotenv('.env.local')

# Obtener configuración de la base de datos
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'Laurana@01')
DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
DB_PORT = os.getenv('POSTGRES_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'clip_comparador_v2')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def insert_sample_configs():
    """Inserta configuraciones de atributos de ejemplo para el primer cliente"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Obtener el primer cliente
        result = conn.execute(text("SELECT id, name FROM clients LIMIT 1"))
        client = result.fetchone()

        if not client:
            print("❌ No se encontró ningún cliente en la base de datos")
            print("   Primero debes crear un cliente en el sistema")
            return

        client_id = client[0]
        client_name = client[1]

        print(f"✅ Cliente encontrado: {client_name} (ID: {client_id})")
        print("\n🔧 Insertando configuraciones de atributos de ejemplo...\n")

        # Atributos de ejemplo
        sample_configs = [
            {
                'key': 'material',
                'label': 'Material',
                'type': 'list',
                'required': False,
                'options': ['Algodón', 'Poliéster', 'Lana', 'Seda', 'Lino', 'Mezcla'],
                'field_order': 1
            },
            {
                'key': 'talla',
                'label': 'Talla',
                'type': 'list',
                'required': False,
                'options': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
                'field_order': 2
            },
            {
                'key': 'color',
                'label': 'Color',
                'type': 'text',
                'required': False,
                'options': None,
                'field_order': 3
            },
            {
                'key': 'temporada',
                'label': 'Temporada',
                'type': 'list',
                'required': False,
                'options': ['Primavera/Verano', 'Otoño/Invierno', 'Todo el año'],
                'field_order': 4
            },
            {
                'key': 'genero',
                'label': 'Género',
                'type': 'list',
                'required': False,
                'options': ['Hombre', 'Mujer', 'Unisex', 'Niño', 'Niña'],
                'field_order': 5
            },
            {
                'key': 'marca',
                'label': 'Marca',
                'type': 'text',
                'required': False,
                'options': None,
                'field_order': 6
            },
            {
                'key': 'url_proveedor',
                'label': 'URL del Proveedor',
                'type': 'url',
                'required': False,
                'options': None,
                'field_order': 7
            },
            {
                'key': 'fecha_ingreso',
                'label': 'Fecha de Ingreso',
                'type': 'date',
                'required': False,
                'options': None,
                'field_order': 8
            },
            {
                'key': 'peso_kg',
                'label': 'Peso (kg)',
                'type': 'number',
                'required': False,
                'options': None,
                'field_order': 9
            },
        ]

        # Verificar si ya existen configuraciones para este cliente
        result = conn.execute(
            text("SELECT COUNT(*) FROM product_attribute_config WHERE client_id = :client_id"),
            {"client_id": client_id}
        )
        existing_count = result.fetchone()[0]

        if existing_count > 0:
            print(f"⚠️  El cliente ya tiene {existing_count} configuraciones de atributos")
            response = input("¿Deseas eliminarlas y crear las de ejemplo? (s/n): ")
            if response.lower() != 's':
                print("❌ Operación cancelada")
                return

            # Eliminar configuraciones existentes
            conn.execute(
                text("DELETE FROM product_attribute_config WHERE client_id = :client_id"),
                {"client_id": client_id}
            )
            conn.commit()
            print("🗑️  Configuraciones anteriores eliminadas")

        # Insertar nuevas configuraciones
        for config in sample_configs:
            conn.execute(
                text("""
                    INSERT INTO product_attribute_config
                    (client_id, key, label, type, required, options, field_order)
                    VALUES
                    (:client_id, :key, :label, :type, :required, :options::jsonb, :field_order)
                """),
                {
                    "client_id": client_id,
                    "key": config['key'],
                    "label": config['label'],
                    "type": config['type'],
                    "required": config['required'],
                    "options": str(config['options']).replace("'", '"') if config['options'] else None,
                    "field_order": config['field_order']
                }
            )
            print(f"  ✅ {config['label']} ({config['type']})")

        conn.commit()

        print(f"\n✅ Se insertaron {len(sample_configs)} configuraciones de atributos exitosamente")
        print(f"\n📋 Resumen:")
        print(f"   Cliente: {client_name}")
        print(f"   Atributos configurados: {len(sample_configs)}")
        print(f"\n💡 Ahora puedes crear o editar productos y verás estos campos personalizados en el formulario")

if __name__ == '__main__':
    try:
        insert_sample_configs()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
