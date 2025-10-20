"""
Parchea demo-store.html para manejar correctamente respuestas 400 del backend
mostrando el mensaje JSON (message/details/available_categories) en lugar de
un genérico "Error 400".

Cambios:
1) showError(err): acepta objeto y renderiza mensaje detallado.
2) searchBtn handler: cuando response.ok=false, intenta leer JSON y llama a showError.
3) displayResults(data): si success=false, llama a showError.
4) Limpia restos de MARKER_START/MARKER_END si quedaron impresos.

El script es idempotente.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.400fix.bak.html'

if not HTML.exists():
    raise SystemExit(f"❌ No se encuentra {HTML}")

orig = HTML.read_text(encoding='utf-8', errors='ignore')
backup_written = False

# 4) Limpiar marcadores impresos si existen
patched = re.sub(r"\bMARKER_START\b|\bMARKER_END\b", "", orig)

if patched != orig:
    if not backup_written:
        BAK.write_text(orig, encoding='utf-8')
        backup_written = True
    orig = patched

content = orig

# 1) Reemplazar showError(message) por showError(err) mejorado
show_error_pattern = re.compile(r"function\s+showError\s*\([^)]*\)\s*\{.*?\}", re.DOTALL)
new_show_error = (
    "function showError(err) {\n"
    "  let msg = '';\n"
    "  if (err && typeof err === 'object') {\n"
    "    if (err.message) msg += err.message + \\\"\\n\\\";\n"
    "    if (err.details) msg += err.details + \\\"\\n\\\";\n"
    "    if (Array.isArray(err.available_categories)) {\n"
    "      msg += \\\"\\nCategorías disponibles:\\\\n- \\\" + err.available_categories.join('\\\\n- ');\n"
    "    }\n"
    "  } else {\n"
    "    msg = String(err || 'Error desconocido');\n"
    "  }\n"
    "  const el = document.getElementById('errorMessage');\n"
    "  const tx = document.getElementById('errorText');\n"
    "  if (tx) tx.textContent = msg.trim();\n"
    "  if (el) el.classList.add('active');\n"
    "  const rs = document.getElementById('resultsSection');\n"
    "  if (rs) rs.classList.remove('active');\n"
    "}\n"
)

if show_error_pattern.search(content):
    patched = show_error_pattern.sub(new_show_error, content)
    if patched != content:
        if not backup_written:
            BAK.write_text(content, encoding='utf-8')
            backup_written = True
        content = patched

# 2) Modificar el bloque tras el fetch dentro del click handler
# Buscamos el patrón convencional donde se maneja response.ok y se hace "const data = await response.json();"
fetch_block_pattern = re.compile(
    r"const\s+response\s*=\s*await\s*fetch\([^)]*\)\s*;\s*"  # fetch
    r"(.*?)"  # contenido intermedio
    r"if\s*\(!response\.ok\)\s*\{\s*throw\s+new\s+Error\([^}]*\)\s*;\s*\}\s*"  # if (!response.ok) throw
    r"const\s+data\s*=\s*await\s*response\.json\(\)\s*;\s*"  # const data = await response.json();
    r"displayResults\(data\)\s*;",
    re.DOTALL
)

replacement_fetch_block = (
    "const response = await fetch(API_URL, {\n"
    "    method: 'POST',\n"
    "    headers: { 'X-API-Key': API_KEY },\n"
    "    body: formData\n"
    "});\n\n"
    "let data;\n"
    "try { data = await response.json(); } catch (_) { data = null; }\n\n"
    "if (!response.ok) {\n"
    "  showError(data || { message: `Error ${response.status}: ${response.statusText}` });\n"
    "  return;\n"
    "}\n"
    "displayResults(data);"
)

content2, nrep = fetch_block_pattern.subn(replacement_fetch_block, content)
if nrep > 0:
    if not backup_written:
        BAK.write_text(content, encoding='utf-8')
        backup_written = True
    content = content2

# 3) Asegurar guard en displayResults
# Insertar al inicio del cuerpo de displayResults
display_header_pattern = re.compile(r"function\s+displayResults\s*\(\s*data\s*\)\s*\{")
if display_header_pattern.search(content):
    guard = (
        "function displayResults(data) {\n"
        "  if (!data || data.success === false) {\n"
        "    showError(data || 'Respuesta inválida');\n"
        "    return;\n"
        "  }"
    )
    content2 = display_header_pattern.sub(guard, content, count=1)
    if content2 != content:
        if not backup_written:
            BAK.write_text(content, encoding='utf-8')
            backup_written = True
        content = content2

# Escribir si hubo cambios
if content != orig:
    HTML.write_text(content, encoding='utf-8')
    print(f"✅ Parche aplicado. Backup: {BAK}")
else:
    print("ℹ️ Nada para cambiar (quizás ya está aplicado)")
