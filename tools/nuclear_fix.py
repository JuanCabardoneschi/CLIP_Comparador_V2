"""
Solución nuclear: Busca y elimina TODOS los bloques de JavaScript relacionados
con showError y los reemplaza con una única implementación limpia.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.nuclear.bak.html'

if not HTML.exists():
    raise SystemExit(f"No se encuentra {HTML}")

content = HTML.read_text(encoding='utf-8', errors='ignore')
BAK.write_text(content, encoding='utf-8')

print("Aplicando solución nuclear...")

# 1. Encontrar el último </script> antes de </body>
# Vamos a eliminar TODO desde el primer "showError" hasta ese </script>

# Buscar el índice del primer cierre de script principal (donde está el código de búsqueda)
# Esto debería estar después de toda la lógica de displayResults, formatAttribute, etc.

# Estrategia: Buscar el comentario que indica el fin del script principal
main_script_end = content.find('</script>')
if main_script_end == -1:
    raise SystemExit("No se encontró </script>")

# Ahora buscar hacia atrás desde </body> para encontrar todos los scripts basura
body_end = content.find('</body>')
if body_end == -1:
    raise SystemExit("No se encontró </body>")

# Extraer la sección entre el primer </script> y </body>
problematic_section_start = main_script_end + len('</script>')
problematic_section = content[problematic_section_start:body_end]

# Eliminar TODOS los <script>...</script> en esa sección problemática
cleaned_section = re.sub(r'<script[^>]*>.*?</script>', '', problematic_section, flags=re.DOTALL)

# También eliminar el {} suelto
cleaned_section = cleaned_section.replace('\n{}\n', '\n')
cleaned_section = cleaned_section.replace('\n{}\r\n', '\n')

# Reconstruir el contenido
before_problem = content[:problematic_section_start]
after_problem = content[body_end:]

# Script limpio para insertar
clean_script = '''

<!-- DEMO-STORE: ERROR HANDLING OVERRIDE -->
<script>
(function() {
  // Override de showError para mostrar mensajes detallados del backend
  window.showError = function(err) {
    var msg = '';

    if (err && typeof err === 'object') {
      if (err.message) {
        msg += err.message + '\\n';
      }
      if (err.details) {
        msg += err.details + '\\n';
      }
      if (Array.isArray(err.available_categories) && err.available_categories.length > 0) {
        msg += '\\nCategorías disponibles:\\n- ' + err.available_categories.join('\\n- ');
      }
    } else {
      msg = String(err || 'Error desconocido');
    }

    var errorText = document.getElementById('errorText');
    var errorMessage = document.getElementById('errorMessage');
    var resultsSection = document.getElementById('resultsSection');

    if (errorText) {
      errorText.textContent = msg.trim();
    }
    if (errorMessage) {
      errorMessage.classList.add('active');
    }
    if (resultsSection) {
      resultsSection.classList.remove('active');
    }
  };

  console.log('✅ Error handler override instalado');
})();
</script>
'''

new_content = before_problem + cleaned_section + clean_script + '\n' + after_problem

HTML.write_text(new_content, encoding='utf-8')
print(f"✅ Solución nuclear aplicada. Backup: {BAK}")
print("   Recarga con Ctrl+F5 y verifica la consola.")
