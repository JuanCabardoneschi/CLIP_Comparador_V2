"""
Script para generar y actualizar tags de productos automáticamente
"""
import os
import re
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

# Escapar caracteres especiales en la contraseña
from urllib.parse import quote_plus
DB_PASSWORD_ESCAPED = quote_plus(DB_PASSWORD)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD_ESCAPED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Diccionarios de palabras clave por categoría
COLORES = {
    'negro': 'negro', 'negra': 'negro', 'black': 'negro',
    'blanco': 'blanco', 'blanca': 'blanco', 'white': 'blanco',
    'azul': 'azul', 'blue': 'azul',
    'rojo': 'rojo', 'roja': 'rojo', 'red': 'rojo',
    'verde': 'verde', 'green': 'verde',
    'amarillo': 'amarillo', 'amarilla': 'amarillo', 'yellow': 'amarillo',
    'gris': 'gris', 'grey': 'gris', 'gray': 'gris',
    'beige': 'beige', 'habano': 'beige', 'caramelo': 'beige',
    'jean': 'jean', 'denim': 'jean',
    'marino': 'azul-marino'
}

TIPOS_PRENDA = {
    'camisa': ['camisa', 'formal', 'trabajo'],
    'casaca': ['casaca', 'chaqueta', 'abrigo'],
    'chaqueta': ['chaqueta', 'abrigo', 'chef'],
    'chaleco': ['chaleco', 'vest'],
    'ambo': ['ambo', 'medico', 'uniforme'],
    'gorra': ['gorra', 'accesorio', 'cabeza'],
    'boina': ['boina', 'accesorio', 'cabeza'],
    'delantal': ['delantal', 'cocina', 'trabajo'],
    'pantalon': ['pantalon', 'bajo'],
    'zapato': ['zapato', 'calzado', 'pies'],
    'buzo': ['buzo', 'casual', 'deportivo'],
    'cardigan': ['cardigan', 'abrigo', 'casual']
}

GENERO = {
    'dama': 'mujer',
    'hombre': 'hombre',
    'unisex': 'unisex'
}

ESTILOS = {
    'slim': 'ajustado',
    'vestir': 'formal',
    'casual': 'casual',
    'chef': 'profesional',
    'medico': 'medico',
    'dry-fit': 'deportivo'
}

def generar_tags(nombre, descripcion, color, brand, categoria_nombre):
    """Genera tags basándose en el producto"""
    tags = set()

    # Convertir a minúsculas para análisis
    texto = f"{nombre} {descripcion or ''} {categoria_nombre or ''}".lower()

    # 1. Agregar marca si existe
    if brand:
        tags.add(brand.lower())

    # 2. Detectar colores
    if color:
        color_norm = color.lower()
        if color_norm in COLORES:
            tags.add(COLORES[color_norm])
        else:
            tags.add(color_norm)

    # Buscar colores en el texto
    for color_key, color_tag in COLORES.items():
        if color_key in texto:
            tags.add(color_tag)
            break

    # 3. Detectar tipo de prenda
    for tipo, tipo_tags in TIPOS_PRENDA.items():
        if tipo in texto:
            tags.update(tipo_tags[:2])  # Agregar primeros 2 tags del tipo
            break

    # 4. Detectar género
    for genero_key, genero_tag in GENERO.items():
        if genero_key in texto:
            tags.add(genero_tag)
            break

    # 5. Detectar estilo
    for estilo_key, estilo_tag in ESTILOS.items():
        if estilo_key in texto:
            tags.add(estilo_tag)

    # 6. Agregar categoría simplificada
    if categoria_nombre:
        cat_simple = categoria_nombre.lower().split('-')[0].split('–')[0].strip()
        if len(cat_simple) > 3:
            tags.add(cat_simple)

    # 7. Agregar tags generales según el tipo
    if any(palabra in texto for palabra in ['camisa', 'casaca', 'chaqueta', 'ambo']):
        tags.add('uniforme')

    if any(palabra in texto for palabra in ['gorra', 'boina']):
        tags.add('accesorio')

    # Convertir a lista y ordenar
    return ', '.join(sorted(list(tags)))

def actualizar_tags():
    """Actualiza los tags de todos los productos"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Obtener todos los productos con sus categorías
        result = conn.execute(text("""
            SELECT p.id, p.name, p.description, p.color, p.brand, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.name
        """))

        productos = result.fetchall()

        print(f"📦 Procesando {len(productos)} productos...\n")

        actualizados = 0
        for producto in productos:
            product_id, nombre, descripcion, color, brand, categoria = producto

            # Generar tags
            tags = generar_tags(nombre, descripcion, color, brand, categoria)

            if tags:
                # Actualizar en la base de datos
                conn.execute(
                    text("UPDATE products SET tags = :tags WHERE id = :id"),
                    {"tags": tags, "id": product_id}
                )
                actualizados += 1
                print(f"✅ {nombre[:40]:40} → {tags}")
            else:
                print(f"⚠️  {nombre[:40]:40} → (sin tags)")

        conn.commit()

        print(f"\n✅ Actualización completada: {actualizados}/{len(productos)} productos con tags")

if __name__ == '__main__':
    try:
        actualizar_tags()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
