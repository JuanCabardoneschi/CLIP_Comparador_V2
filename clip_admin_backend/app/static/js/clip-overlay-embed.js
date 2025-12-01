/*
 * CLIP Overlay Embed Wrapper (usa el widget unificado existente)
 *
 * Inserción mínima recomendada en el sitio del cliente:
 * <script src="https://TU_DOMINIO/static/js/clip-overlay-embed.js"
 *         data-api-key="pk_XXXX"
 *         data-endpoint="https://api.clipv2.com"
 *         data-auto-mount="true"></script>
 * <button data-clip-trigger="true">Buscar por imagen o texto</button>
 *
 * Este wrapper crea un overlay modal y, en el primer uso, carga
 * dinámicamente /static/js/clip-widget-embed-unified.js y lo monta
 * dentro del modal. En aperturas siguientes, re‑utiliza el mismo
 * contenedor para evitar recargar scripts.
 */
(function(){
  'use strict';

  // Utilidades básicas
  function $(sel, parent){ return (parent||document).querySelector(sel); }
  function createEl(tag, attrs){
    const el = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, v));
    return el;
  }

  // Obtener configuración desde el <script> actual (data-*)
  var currentScript = document.currentScript || (function(){
    const scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();

  var DATA = {
    apiKey: currentScript.getAttribute('data-api-key') || (window.CLIPWidget && window.CLIPWidget.apiKey) || '',
    endpoint: currentScript.getAttribute('data-endpoint') || (window.CLIPWidget && window.CLIPWidget.serverUrl) || 'https://clipcomparadorv2-production.up.railway.app',
    autoMount: (currentScript.getAttribute('data-auto-mount')||'').toLowerCase() === 'true'
  };

  if(!DATA.apiKey){
    console.warn('CLIP Overlay: falta data-api-key en la etiqueta <script>');
  }

  // Estado interno
  var overlayRoot = null;
  var widgetContainer = null;
  var widgetLoaded = false; // si ya cargamos el JS del widget unificado
  var unifiedSrc = (function(){
    // Intentar resolver ruta relativa local si existe, de lo contrario permitir absoluta
    // Por defecto usamos la versión local servida por Flask static
    return '/static/js/clip-widget-embed-unified.js';
  })();

  function buildOverlay(){
    if(overlayRoot) return overlayRoot;

    overlayRoot = createEl('div', { id: 'clip-overlay-root', style: [
      'position:fixed', 'inset:0', 'z-index:2147483000', 'display:none',
      'align-items:center', 'justify-content:center', 'background:rgba(0,0,0,0.5)'
    ].join(';')});

    var modal = createEl('div', { id: 'clip-overlay-modal', style: [
      'background:#fff', 'border-radius:16px', 'max-width:1000px', 'width:95%',
      'max-height:90vh', 'overflow:auto', 'box-shadow:0 20px 60px rgba(0,0,0,0.25)'
    ].join(';')});

    var header = createEl('div', { style: [
      'display:flex','justify-content:space-between','align-items:center',
      'padding:16px 20px','border-bottom:1px solid #e5e7eb',
      'position:sticky','top:0','background:#fff','z-index:10'
    ].join(';')});

    var title = createEl('div', { style: 'font-weight:700;font-size:16px;color:#111827' });
    title.textContent = 'Búsqueda por imagen o texto';

    var closeBtn = createEl('button', { type: 'button', 'aria-label':'Cerrar', style: [
      'border:none','background:transparent','cursor:pointer','font-size:22px','line-height:1','padding:4px'
    ].join(';')});
    closeBtn.textContent = '×';

    header.appendChild(title);
    header.appendChild(closeBtn);
    modal.appendChild(header);

    // Contenedor del widget existente
    widgetContainer = createEl('div', { id: 'clip-widget-overlay-container', style: 'padding:16px' });
    modal.appendChild(widgetContainer);

    overlayRoot.appendChild(modal);
    document.body.appendChild(overlayRoot);

    // Cerrar overlay
    function hide(){ overlayRoot.style.display = 'none'; }
    closeBtn.addEventListener('click', hide);
    overlayRoot.addEventListener('click', function(e){ if(e.target === overlayRoot) hide(); });

    return overlayRoot;
  }

  function ensureWidgetLoaded(){
    if(widgetLoaded) return Promise.resolve();
    return new Promise(function(resolve, reject){
      var s = createEl('script');
      s.src = unifiedSrc + '?v=' + Date.now(); // cache-busting en primera carga
      s.async = true;
      s.onload = function(){ widgetLoaded = true; resolve(); };
      s.onerror = function(){ reject(new Error('No se pudo cargar el widget unificado')); };
      document.head.appendChild(s);
    });
  }

  function openOverlay(){
    buildOverlay();

    // Configurar para el widget unificado existente
    window.CLIPWidget = {
      apiKey: DATA.apiKey,
      serverUrl: DATA.endpoint,
      containerId: 'clip-widget-overlay-container'
    };

    // Si ya cargamos el widget anteriormente, sólo mostrar (el DOM persiste)
    if(widgetLoaded){
      overlayRoot.style.display = 'flex';
      return;
    }

    // Cargar y luego mostrar
    ensureWidgetLoaded()
      .then(function(){ overlayRoot.style.display = 'flex'; })
      .catch(function(err){
        console.error('CLIP Overlay: error cargando widget unificado', err);
        alert('No se pudo cargar el buscador. Intenta nuevamente más tarde.');
      });
  }

  function bindTriggers(){
    document.addEventListener('click', function(e){
      var el = e.target.closest('[data-clip-trigger="true"]');
      if(!el) return;
      e.preventDefault();
      openOverlay();
    });
  }

  // Auto-bind si el integrador usa data-auto-mount
  function init(){
    bindTriggers();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // API pública opcional
  window.CLIPV2 = window.CLIPV2 || {};
  window.CLIPV2.overlay = {
    open: openOverlay,
    isLoaded: function(){ return !!widgetLoaded; }
  };
})();
