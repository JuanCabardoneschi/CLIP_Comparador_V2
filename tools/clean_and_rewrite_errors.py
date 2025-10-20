"""
Elimina TODAS las funciones problemáticas de manejo de errores
y las reemplaza con un único bloque limpio al final antes de </body>.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.clean_rewrite.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')
BAK.write_text(content, encoding='utf-8')

print("Limpiando funciones defectuosas...")

# 1. Eliminar TODAS las definiciones de showError defectuosas
# Buscar desde "function showError" hasta el siguiente cierre de función
pattern_showerror = re.compile(
    r'function\s+showError\s*\([^)]*\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}',
    re.DOTALL
)
content = pattern_showerror.sub('/* showError removed */', content)

# 2. Eliminar bloques de override anteriores si existen
content = re.sub(
    r'<!-- DEMO-STORE ERROR HANDLING OVERRIDE START -->.*?<!-- DEMO-STORE ERROR HANDLING OVERRIDE END -->',
    '',
    content,
    flags=re.DOTALL
)

# 3. Buscar displayResults y asegurar que tenga el guard
# Primero, encontrar la función displayResults
pattern_display = re.compile(
    r'(function\s+displayResults\s*\(\s*data\s*\)\s*\{)\s*',
    re.DOTALL
)

# Agregar el guard al inicio si no existe
def add_guard(match):
    func_start = match.group(1)
    return func_start + '''
            if (!data || data.success === false) {
                showError(data || 'Respuesta inválida');
                return;
            }'''

if 'if (!data || data.success === false)' not in content:
    content = pattern_display.sub(add_guard, content, count=1)

# 4. Insertar el bloque de override limpio antes de </body>
clean_override = '''

<!-- DEMO-STORE ERROR HANDLING OVERRIDE -->
<script>
(function() {
  // showError mejorado
  window.showError = function(err) {
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
    const errorText = document.getElementById('errorText');
    const errorMessage = document.getElementById('errorMessage');
    const resultsSection = document.getElementById('resultsSection');
    if (errorText) errorText.textContent = msg.trim();
    if (errorMessage) errorMessage.classList.add('active');
    if (resultsSection) resultsSection.classList.remove('active');
  };
})();
</script>
'''

# Insertar antes de </body>
if '</body>' in content:
    content = content.replace('</body>', clean_override + '\n</body>')
else:
    content += clean_override

HTML.write_text(content, encoding='utf-8')
print(f"✅ Código limpiado y reescrito. Backup: {BAK}")
print("   Recarga la página (Ctrl+F5) y verifica la consola.")
