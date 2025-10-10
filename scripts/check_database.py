#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar Estructura de Base de Datos
Ver qué tablas y columnas existen en la BD
"""
import os
import sys
import sqlite3
from pathlib import Path

# Configurar el proyecto
project_root = Path(__file__).parent.parent
backend_dir = project_root / "clip_admin_backend"
os.chdir(backend_dir)

def check_database_structure():
    """Verificar la estructura de la base de datos"""
    print("🔍 VERIFICANDO ESTRUCTURA DE BASE DE DATOS")
    print("="*50)

    # Buscar archivos de base de datos
    db_files = [
        backend_dir / "instance" / "clip_comparador_v2.db",
        project_root / "clip_comparador_v2.db",
        project_root / "instance" / "clip_comparador_v2.db"
    ]

    db_path = None
    for db_file in db_files:
        if db_file.exists():
            db_path = db_file
            break

    if not db_path:
        print("❌ No se encontró archivo de base de datos")
        print("📋 Buscado en:")
        for db_file in db_files:
            print(f"   - {db_file}")
        return False

    print(f"📄 Base de datos encontrada: {db_path}")
    print(f"📊 Tamaño: {db_path.stat().st_size / 1024:.2f} KB")

    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Obtener lista de tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print(f"\\n📊 Tablas encontradas: {len(tables)}")

        for table_name, in tables:
            print(f"\\n📋 Tabla: {table_name}")

            # Obtener estructura de la tabla
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()

            for col in columns:
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                pk_marker = " [PK]" if is_pk else ""
                null_marker = " [NOT NULL]" if not_null else ""
                default_marker = f" [DEFAULT: {default_val}]" if default_val else ""
                print(f"   📄 {col_name}: {col_type}{pk_marker}{null_marker}{default_marker}")

            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"   📊 Registros: {count}")

            # Si es una tabla de productos o similar, mostrar algunos ejemplos
            if 'product' in table_name.lower() or 'item' in table_name.lower():
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                samples = cursor.fetchall()
                if samples:
                    print(f"   🔍 Ejemplos:")
                    for sample in samples:
                        print(f"      {sample}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error al acceder a la base de datos: {e}")
        return False

if __name__ == "__main__":
    check_database_structure()
