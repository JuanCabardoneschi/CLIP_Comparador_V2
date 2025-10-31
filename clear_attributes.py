"""
Script para limpiar todos los atributos JSONB de productos
Esto permite reiniciar el proceso de clasificación automática desde cero
"""
print("INICIO DEL SCRIPT - Limpiar Atributos JSONB")

try:
    import os
    import psycopg2
    from dotenv import load_dotenv

    print("Módulos importados correctamente")

    # Cargar variables de entorno
    load_dotenv('.env.local')
    DATABASE_URL = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {DATABASE_URL}")

    # Conectar a la base de datos
    print("\nConectando a la base de datos...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("Conexión exitosa")

    # Contar productos con atributos antes de limpiar
    cursor.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE attributes IS NOT NULL AND attributes != '{}' AND attributes != '[]'
    """)
    count_before = cursor.fetchone()[0]
    print(f"\nProductos con atributos actualmente: {count_before}")

    # Preguntar confirmación
    if count_before > 0:
        print("\n⚠️  ADVERTENCIA: Esto eliminará TODOS los atributos JSONB de TODOS los productos.")
        confirm = input("¿Estás seguro de continuar? (escribe 'SI' para confirmar): ")

        if confirm.strip().upper() != 'SI':
            print("\nOperación cancelada por el usuario.")
            cursor.close()
            conn.close()
            exit(0)

    # Limpiar atributos
    print("\nLimpiando atributos JSONB...")
    cursor.execute("""
        UPDATE products
        SET attributes = '{}'::jsonb
        WHERE attributes IS NOT NULL
    """)

    rows_updated = cursor.rowcount
    conn.commit()

    print(f"✓ Atributos limpiados: {rows_updated} productos actualizados")

    # Verificar resultado
    cursor.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE attributes IS NOT NULL AND attributes != '{}' AND attributes != '[]'
    """)
    count_after = cursor.fetchone()[0]
    print(f"Productos con atributos después de limpiar: {count_after}")

    print("\n" + "="*60)
    print("LIMPIEZA COMPLETADA EXITOSAMENTE")
    print("Ahora puedes ejecutar auto_fill_attributes.py para regenerar los atributos")
    print("="*60)

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\nERROR FATAL: {e}")
    import traceback
    traceback.print_exc()
