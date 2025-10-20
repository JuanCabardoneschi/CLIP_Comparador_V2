"""
Busca y arregla TODOS los bloques de código JavaScript mal escapados
en demo-store.html (hay múltiples ocurrencias del mismo problema).
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.alljs_fix.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')
BAK.write_text(content, encoding='utf-8')

# Arreglar todos los patrones problemáticos

# 1. Líneas rotas con saltos de línea escapados incorrectamente
# Patrón: texto + ' seguido de salto de línea y luego '; en la siguiente línea
content = re.sub(r"(\w+\s*\+=\s*\w+\.\w+\s*\+\s*)'\\n'\n\s*';", r"\1'\\n';", content)
content = re.sub(r"(\w+\s*\+=\s*)'\\n'\n\s*';", r"\1'\\n';", content)

# 2. Dobles llaves {{ en lugar de {
content = content.replace('{{', '{').replace('}}', '}')

# 3. Texto roto en múltiples líneas
lines = content.split('\n')
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]

    # Si la línea termina con + ' o + " y no tiene cierre
    if re.search(r"\+\s*['\"]$", line.strip()) and i + 1 < len(lines):
        next_line = lines[i + 1].strip()
        # Si la siguiente línea es solo '; o ";, consolidar
        if next_line in ["';", '";', "\\';", '\";']:
            line = line.rstrip() + "';"
            i += 2  # Saltar la siguiente línea
            fixed_lines.append(line)
            continue

    fixed_lines.append(line)
    i += 1

content = '\n'.join(fixed_lines)

HTML.write_text(content, encoding='utf-8')
print(f"✅ Todos los errores JS arreglados. Backup: {BAK}")
print(f"   Revisa la consola del navegador para confirmar.")
