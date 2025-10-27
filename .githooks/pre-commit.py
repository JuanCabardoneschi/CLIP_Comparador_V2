#!/usr/bin/env python3
"""
Script de validación pre-commit para Python
Valida sintaxis de TODOS los archivos Python antes de permitir commit
"""
import sys
import py_compile
import subprocess
from pathlib import Path

def get_staged_python_files():
    """Obtiene lista de archivos .py staged para commit"""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )
        files = [f for f in result.stdout.strip().split('\n') if f.endswith('.py') and f]
        return files
    except subprocess.CalledProcessError:
        return []

def validate_syntax(filepath):
    """Valida sintaxis de un archivo Python"""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)

def main():
    print("🔍 Validando sintaxis de archivos Python...")
    
    staged_files = get_staged_python_files()
    
    if not staged_files:
        print("✅ No hay archivos Python en este commit")
        return 0
    
    has_errors = False
    
    for filepath in staged_files:
        if not Path(filepath).exists():
            continue
            
        print(f"   Compilando: {filepath}")
        is_valid, error = validate_syntax(filepath)
        
        if not is_valid:
            print(f"❌ ERROR DE SINTAXIS en: {filepath}")
            print(f"   {error}")
            has_errors = True
    
    if has_errors:
        print("\n" + "❌" * 40)
        print("❌ COMMIT BLOQUEADO: Hay errores de sintaxis en archivos Python")
        print("❌ Arregla los errores antes de hacer commit")
        print("❌" * 40 + "\n")
        return 1
    
    print("✅ Todos los archivos Python tienen sintaxis válida")
    return 0

if __name__ == '__main__':
    sys.exit(main())
