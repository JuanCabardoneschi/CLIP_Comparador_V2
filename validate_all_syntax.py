#!/usr/bin/env python3
"""
Validador de sintaxis Python para todo el proyecto
Ejecuta ANTES de commit para detectar errores de sintaxis

Uso:
    python validate_all_syntax.py
"""
import py_compile
from pathlib import Path
from colorama import init, Fore, Style

# Inicializar colorama para colores en Windows
init()

def validate_project():
    """Valida sintaxis de todos los archivos Python del proyecto"""
    
    print(f"\n{Fore.CYAN}🔍 VALIDACIÓN DE SINTAXIS - CLIP Comparador V2{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
    
    # Buscar todos los archivos .py
    project_root = Path(__file__).parent
    python_files = []
    
    for pattern in ['clip_admin_backend/**/*.py', 'shared/**/*.py', 'tools/**/*.py']:
        python_files.extend(project_root.glob(pattern))
    
    # Filtrar archivos en __pycache__ y venv
    python_files = [
        f for f in python_files 
        if '__pycache__' not in str(f) and 'venv' not in str(f)
    ]
    
    print(f"\n{Fore.YELLOW}📋 Archivos a validar: {len(python_files)}{Style.RESET_ALL}\n")
    
    has_errors = False
    error_files = []
    
    for filepath in sorted(python_files):
        relative_path = filepath.relative_to(project_root)
        print(f"   Compilando: {relative_path}", end=" ")
        
        try:
            py_compile.compile(str(filepath), doraise=True)
            print(f"{Fore.GREEN}✅ OK{Style.RESET_ALL}")
        except py_compile.PyCompileError as e:
            print(f"{Fore.RED}❌ ERROR{Style.RESET_ALL}")
            print(f"{Fore.RED}   {e}{Style.RESET_ALL}")
            has_errors = True
            error_files.append(str(relative_path))
    
    print(f"\n{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")
    
    if has_errors:
        print(f"{Fore.RED}❌ VALIDACIÓN FALLIDA{Style.RESET_ALL}")
        print(f"\n{Fore.RED}Archivos con errores:{Style.RESET_ALL}")
        for file in error_files:
            print(f"{Fore.RED}   - {file}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}⚠️  NO HAGAS COMMIT HASTA ARREGLAR ESTOS ERRORES ⚠️{Style.RESET_ALL}\n")
        return 1
    else:
        print(f"{Fore.GREEN}✅ TODOS LOS ARCHIVOS SON VÁLIDOS{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   Puedes hacer commit con seguridad{Style.RESET_ALL}\n")
        return 0

if __name__ == '__main__':
    import sys
    sys.exit(validate_project())
