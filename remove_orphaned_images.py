#!/usr/bin/env python3
"""
Script para eliminar imágenes huérfanas del sistema CLIP Comparador V2.
Elimina archivos que están en el directorio pero no están asociados con ningún producto.
"""

import os
import sqlite3
from pathlib import Path

def remove_orphaned_images():
    """Elimina imágenes huérfanas del directorio de uploads."""

    print("🗑️ ELIMINANDO IMÁGENES HUÉRFANAS...")
    print()

    # Configuración de rutas
    db_path = "./clip_admin_backend/instance/clip_comparador_v2.db"
    upload_dir = Path("./clip_admin_backend/static/uploads/clients/demo_fashion_store")

    # Verificar que el directorio existe
    if not upload_dir.exists():
        print(f"❌ Error: Directorio no existe: {upload_dir}")
        return

    # Obtener todas las imágenes registradas en la base de datos
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Obtener todos los filenames de la tabla images
        cursor.execute("SELECT filename FROM images")
        db_images = {row[0] for row in cursor.fetchall()}

        print(f"📊 Imágenes en base de datos: {len(db_images)}")

        conn.close()

    except Exception as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        return

    # Obtener todos los archivos del directorio
    all_files = [f for f in upload_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]
    print(f"📁 Archivos en directorio: {len(all_files)}")
    print()

    # Identificar archivos huérfanos
    orphaned_files = []
    for file_path in all_files:
        filename = file_path.name
        if filename not in db_images:
            orphaned_files.append(file_path)

    if not orphaned_files:
        print("✅ No hay imágenes huérfanas para eliminar.")
        return

    print(f"🗂️ ARCHIVOS HUÉRFANOS ENCONTRADOS: {len(orphaned_files)}")
    print()

    # Mostrar lista de archivos a eliminar
    for i, file_path in enumerate(orphaned_files, 1):
        # Extraer el nombre base sin UUID
        filename = file_path.name
        if '_' in filename:
            base_name = filename.split('_', 1)[1] if len(filename.split('_', 1)) > 1 else filename
        else:
            base_name = filename

        print(f"   {i:2d}. {filename}")
        print(f"       → {base_name}")

    print()

    # Confirmación de eliminación
    response = input("¿Deseas eliminar estos archivos? (y/N): ").strip().lower()

    if response not in ['y', 'yes', 'sí', 's']:
        print("❌ Operación cancelada.")
        return

    # Eliminar archivos
    deleted_count = 0
    deleted_size = 0

    print()
    print("🗑️ ELIMINANDO ARCHIVOS...")

    for file_path in orphaned_files:
        try:
            # Obtener tamaño del archivo antes de eliminarlo
            file_size = file_path.stat().st_size

            # Eliminar archivo
            file_path.unlink()

            deleted_count += 1
            deleted_size += file_size

            print(f"   ✅ Eliminado: {file_path.name}")

        except Exception as e:
            print(f"   ❌ Error eliminando {file_path.name}: {e}")

    # Convertir bytes a MB
    deleted_size_mb = deleted_size / (1024 * 1024)

    print()
    print("📊 RESUMEN DE ELIMINACIÓN:")
    print(f"   • Archivos eliminados: {deleted_count}")
    print(f"   • Espacio liberado: {deleted_size_mb:.2f} MB")
    print()

    # Verificación final
    remaining_files = [f for f in upload_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]
    print(f"📁 Archivos restantes en directorio: {len(remaining_files)}")
    print(f"🗄️ Imágenes registradas en base de datos: {len(db_images)}")

    if len(remaining_files) == len(db_images):
        print("✅ ¡Perfecto! Ahora todos los archivos tienen un producto asociado.")
    else:
        print("⚠️ Aún hay discrepancias entre archivos y base de datos.")

    print()
    print("✅ Proceso de eliminación completado.")

if __name__ == "__main__":
    remove_orphaned_images()
