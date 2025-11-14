/**
 * CLIP Widget V3 - Redirección a Página de Búsqueda
 *
 * El cliente usa su propio botón y llama a window.CLIPWidget.open()
 *
 * Uso:
 * <script>
 *   window.CLIPWidget = {
 *     apiKey: "YOUR_KEY",
 *     serverUrl: "https://..."
 *   };
 * </script>
 * <div id="clip-widget"></div>
 * <script src="/static/js/clip-widget-embed-v3.js"></script>
 *
 * Luego desde el botón del cliente:
 * <button onclick="window.CLIPWidget.open()">Buscar con IA</button>
 */

(function() {
    'use strict';

    if (!window.CLIPWidget || !window.CLIPWidget.apiKey) {
        console.error('CLIP Widget: Se requiere window.CLIPWidget = { apiKey: "YOUR_KEY" }');
        return;
    }

    // Configuración
    const config = {
        apiKey: window.CLIPWidget.apiKey,
        serverUrl: window.CLIPWidget.serverUrl || 'https://clipcomparadorv2-production.up.railway.app'
    };

    // Función pública para abrir la búsqueda
    window.CLIPWidget.open = function() {
        const returnUrl = encodeURIComponent(window.location.href);
        const searchUrl = `${config.serverUrl}/widget/search?api_key=${config.apiKey}&return_url=${returnUrl}`;

        console.log('🔍 Abriendo búsqueda CLIP en:', searchUrl);
        window.location.href = searchUrl;
    };

    // Alias para compatibilidad
    window.CLIPWidget.show = window.CLIPWidget.open;
    window.CLIPWidget.start = window.CLIPWidget.open;

    console.log('✅ CLIP Widget V3 inicializado. Usa window.CLIPWidget.open() para abrir búsqueda.');
})();
