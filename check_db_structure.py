#!/usr/bin/env python3
"""
Script para verificar estructura de base de datos
"""
import sqlite3
import os

# Ruta a la base de datos
db_path = 'clip_comparador_v2.db'

if not os.path.exists(db_path):
    print(f"❌ Base de datos no encontrada: {db_path}")
    exit(1)

# Conectar a la base de datos
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar estructura de tabla users
print("🔍 ESTRUCTURA DE TABLA USERS:")
print("=" * 50)
cursor.execute("PRAGMA table_info(users)")
users_columns = cursor.fetchall()

for row in users_columns:
    print(f"  {row[1]:15} | {row[2]:10} | NULL: {row[3]} | Default: {row[4]}")

print("\n📊 DATOS DE USUARIOS:")
print("=" * 50)
cursor.execute("SELECT id, email, role, is_active FROM users")
users_data = cursor.fetchall()

for user in users_data:
    print(f"  ID: {user[0][:8]}... | Email: {user[1]:20} | Role: {user[2]:12} | Active: {user[3]}")

conn.close()
print("\n✅ Verificación completada")