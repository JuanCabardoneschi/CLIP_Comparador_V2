"""
Aplica un parche no intrusivo a demo-store.html para mostrar mensajes detallados
cuando la API devuelve 400 (mismo comportamiento que test-widget-railway.html).

No reescribe grandes bloques: añade un <script> al final que:
- Sobrescribe showError y displayResults con versiones mejoradas
- "Envuelve" window.fetch para que, si la respuesta es 4xx, entregue el JSON
  de error al flujo existente (evitando el throw previo del código original)

Es idempotente: si el parche ya existe, no duplica.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'demo-store.html'
BAK = ROOT / 'demo-store.errorpatch.bak.html'

MARKER_START = '<!-- DEMO-STORE ERROR HANDLING OVERRIDE START -->'
MARKER_END = '<!-- DEMO-STORE ERROR HANDLING OVERRIDE END -->'

OVERRIDE = """
{MARKER_START}
<script>
// Reemplazos ligeros para mostrar mensajes detallados del backend
(function() {{
  // 1) showError mejorado
  window.showError = function(err) {{
    try {{
      var msg = '';
      if (err && typeof err === 'object') {{
        if (err.message) msg += err.message + '\n';
        if (err.details) msg += err.details + '\n';
        if (Array.isArray(err.available_categories)) {{
          msg += '\nCategorías disponibles:\n- ' + err.available_categories.join('\n- ');
        }}
      }} else {{
        msg = String(err || 'Error desconocido');
      }}
      var el = document.getElementById('errorMessage');
      var tx = document.getElementById('errorText');
      if (tx) tx.textContent = msg.trim();
      if (el) el.classList.add('active');
    }} catch (e) {{
      console.warn('showError fallback', e);
    }}
  }};

  // 2) displayResults que respeta success=false
  window.displayResults = function(data) {{
    try {{
      var grid = document.getElementById('resultsGrid');
      var section = document.getElementById('resultsSection');
      var count = document.getElementById('resultsCount');
      if (grid) grid.innerHTML = '';

      if (!data || data.success === false) {{
        window.showError(data || 'Respuesta inválida');
        return;
      }}
      if (!data.results || data.results.length === 0) {{
        window.showError('No se encontraron productos similares. Intenta con otra imagen.');
        return;
      }}
      if (count) count.textContent = `${data.results.length} productos encontrados • Tiempo: ${data.processing_time}`;
      if (section) section.classList.add('active');

      data.results.forEach(function(product) {{
        var card = window.createProductCard ? window.createProductCard(product) : null;
        if (card && grid) grid.appendChild(card);
      }});
      if (section && section.scrollIntoView) section.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }} catch (e) {{
      console.error('displayResults override error', e);
      window.showError(e.message || e);
    }}
  }};

  // 3) Wrapper de fetch: si 4xx, devolver objeto con ok=true y body=JSON de error
  if (window.fetch && !window.__fetchErrorPatched) {{
    var originalFetch = window.fetch;
    window.fetch = async function() {{
      var res = await originalFetch.apply(this, arguments);
      try {{
        if (!res.ok && res.status >= 400) {{
          var data = null;
          try {{ data = await res.clone().json(); }} catch(_) {{}}
          return {{
            ok: true,
            status: 200,
            statusText: 'OK',
            headers: res.headers,
            json: async function() {{ return data || {{ success:false, message: `Error ${res.status}: ${res.statusText}` }}; }}
          }};
        }}
      }} catch(_) {{}}
      return res;
    }};
    window.__fetchErrorPatched = true;
  }}
}})();
</script>
{MARKER_END}
"""

def apply_patch() -> None:
    if not HTML.exists():
        raise SystemExit(f'❌ No se encuentra {HTML}')
    content = HTML.read_text(encoding='utf-8', errors='ignore')

    # Si ya está aplicado, no duplicar
    if MARKER_START in content and MARKER_END in content:
        print('ℹ️ El parche ya estaba presente. No se hicieron cambios.')
        return

    # Insertar antes de </body> si existe, si no, al final
    lower = content.lower()
    idx = lower.rfind('</body>')
    if idx == -1:
        patched = content + '\n' + OVERRIDE + '\n'
    else:
        patched = content[:idx] + OVERRIDE + content[idx:]

    # Backup y escribir
    BAK.write_text(content, encoding='utf-8')
    HTML.write_text(patched, encoding='utf-8')
    print(f'✅ Parche aplicado. Backup: {BAK}')


if __name__ == '__main__':
    apply_patch()
