"""
Limpia los errores de sintaxis JavaScript en demo-store.html
causados por escapes incorrectos de comillas y saltos de línea.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.syntax_fix.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')

# Backup
BAK.write_text(content, encoding='utf-8')

# Arreglar escapes incorrectos en JavaScript
# Reemplazar \" seguido de salto de línea por una cadena normal
fixes = [
    (r'err.message + \"', "err.message + '\\n'"),
    (r'err.details + \"', "err.details + '\\n'"),
    (r'+ \"\\nCategorías disponibles:\\', "+ '\\nCategorías disponibles:\\n- '"),
    (r"+ '\\nCategorías disponibles:\\\\n- '", "+ '\\nCategorías disponibles:\\n- '"),
]

for old, new in fixes:
    content = content.replace(old, new)

# Eliminar líneas rotas (que solo tienen saltos de línea escapados)
lines = content.split('\n')
cleaned = []
i = 0
while i < len(lines):
    line = lines[i]
    # Si la línea solo tiene ";, saltar
    if line.strip() in ['";', "';", '\";', "\';"] and i > 0:
        # La línea anterior debería tener el string completo
        i += 1
        continue
    cleaned.append(line)
    i += 1

content = '\n'.join(cleaned)

HTML.write_text(content, encoding='utf-8')
print(f"Arreglado. Backup: {BAK}")
