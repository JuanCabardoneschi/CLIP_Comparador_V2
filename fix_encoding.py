#!/usr/bin/env python3
"""
Script para arreglar encoding UTF-8 en api.py
Convierte de ISO-8859-1/Latin-1 mal interpretado a UTF-8 correcto
"""
import sys
import os

def fix_encoding(file_path):
    """
    Lee archivo con encoding incorrecto y re-escribe en UTF-8 correcto
    """
    print(f"🔧 Procesando: {file_path}")

    # Backup
    backup_path = file_path + ".backup"
    if os.path.exists(backup_path):
        print(f"⚠️  Backup ya existe: {backup_path}")
        response = input("¿Sobrescribir backup? (s/n): ")
        if response.lower() != 's':
            print("❌ Operación cancelada")
            return False

    # Leer archivo con encoding incorrecto (probablemente Windows-1252 o ISO-8859-1)
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False

    # Crear backup
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Backup creado: {backup_path}")
    except Exception as e:
        print(f"❌ Error creando backup: {e}")
        return False

    # Mapeo de caracteres corruptos comunes
    replacements = {
        # Vocales acentuadas
        'Ã¡': 'á',
        'Ã©': 'é',
        'Ã­': 'í',
        'Ã³': 'ó',
        'Ãº': 'ú',
        'Ã': 'Á',
        'Ã‰': 'É',
        'Ã': 'Í',
        'Ã"': 'Ó',
        'Ãš': 'Ú',

        # Ñ
        'Ã±': 'ñ',
        'Ã'': 'Ñ',

        # Signos de puntuación
        'Â¿': '¿',
        'Â¡': '¡',
        'Âº': 'º',
        'Âª': 'ª',

        # Otros caracteres especiales
        'â€œ': '"',
        'â€': '"',
        'â€™': "'",
        'â€"': '—',
        'â€"': '–',
        'â€¢': '•',
        'â€¦': '…',
        'â‚¬': '€',

        # Emojis y símbolos que aparecen en logs
        'âœ…': '✅',
        'â�': '❌',
        'â�': '⚠',
        'â­': '⭐',
        'â�': '🔧',
        'ðŸ"': '📁',

        'â€˜': "'",
        'â€™': "'",
        'â€œ': '"',
        'â€�': '"',
    }

    # Aplicar reemplazos
    fixed_content = content
    changes_made = 0

    for wrong, correct in replacements.items():
        if wrong in fixed_content:
            count = fixed_content.count(wrong)
            fixed_content = fixed_content.replace(wrong, correct)
            changes_made += count
            print(f"  ✓ Reemplazado '{wrong}' → '{correct}' ({count} veces)")

    if changes_made == 0:
        print("ℹ️  No se encontraron caracteres corruptos")
        return True

    # Escribir archivo corregido
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"✅ Archivo corregido: {changes_made} reemplazos realizados")
        return True
    except Exception as e:
        print(f"❌ Error escribiendo archivo: {e}")
        # Restaurar desde backup
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            print(f"⚠️  Archivo restaurado desde backup")
        except:
            print(f"❌ ERROR CRÍTICO: No se pudo restaurar el backup")
        return False


if __name__ == "__main__":
    # Archivo a procesar
    target_file = "clip_admin_backend/app/blueprints/api.py"

    if not os.path.exists(target_file):
        print(f"❌ Archivo no encontrado: {target_file}")
        sys.exit(1)

    print("=" * 60)
    print("🔧 FIX ENCODING UTF-8 - api.py")
    print("=" * 60)
    print(f"📄 Archivo: {target_file}")
    print(f"📦 Git Tag: pre-encoding-fix-20251110-105301")
    print("=" * 60)
    print()

    # Procesar archivo
    success = fix_encoding(target_file)

    if success:
        print()
        print("=" * 60)
        print("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print(f"📁 Backup guardado en: {target_file}.backup")
        print(f"🔄 Para revertir: git checkout {target_file}")
        print(f"🏷️  O usar tag: git checkout pre-encoding-fix-20251110-105301")
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ PROCESO FALLÓ")
        print("=" * 60)
        print(f"🔄 Revierte con: git checkout {target_file}")
        sys.exit(1)
