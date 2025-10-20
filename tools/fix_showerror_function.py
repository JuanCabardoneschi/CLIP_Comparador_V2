"""
Reemplaza la función showError defectuosa por una versión correcta
usando búsqueda y reemplazo de regex.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.showerror_fix.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')
BAK.write_text(content, encoding='utf-8')

# Buscar y reemplazar la función showError completa
# Patrón: desde "function showError" hasta el cierre "}"
pattern = re.compile(
    r'function\s+showError\s*\([^)]*\)\s*\{.*?\n\s*\}',
    re.DOTALL
)

replacement = """function showError(err) {
            let msg = '';
            if (err && typeof err === 'object') {
                if (err.message) msg += err.message + '\\n';
                if (err.details) msg += err.details + '\\n';
                if (Array.isArray(err.available_categories)) {
                    msg += '\\nCategorías disponibles:\\n- ' + err.available_categories.join('\\n- ');
                }
            } else {
                msg = String(err || 'Error desconocido');
            }
            errorText.textContent = msg.trim();
            errorMessage.classList.add('active');
            resultsSection.classList.remove('active');
        }"""

content_fixed = pattern.sub(replacement, content)

if content_fixed == content:
    print("No se encontró la función showError o ya está correcta")
else:
    HTML.write_text(content_fixed, encoding='utf-8')
    print(f"✅ Función showError arreglada. Backup: {BAK}")
