/**
 * CLIP Comparador - Botón Flotante para Tiendanube
 * Se inyecta automaticamente en todas las paginas de la tienda
 * y abre el modal de CLIP dentro del storefront.
 */
(function() {
    'use strict';

    // Evitar ejecucion multiple
    if (window.CLIP_BUTTON_LOADED) return;
    window.CLIP_BUTTON_LOADED = true;

    const DEFAULT_SERVER_URL = 'https://clipcomparadorv2-production.up.railway.app';
    const WIDGET_SCRIPT_PATH = '/static/js/clip-widget-embed-v4.js';

    const scriptTag = document.currentScript ||
        Array.from(document.getElementsByTagName('script')).find((s) =>
            s.src && s.src.indexOf('tiendanube-floating-button.js') !== -1
        );

    let apiKey = '';
    let serverUrl = DEFAULT_SERVER_URL;
    let isLoadingWidget = false;

    if (scriptTag && scriptTag.src) {
        try {
            const scriptUrl = new URL(scriptTag.src);
            apiKey = scriptUrl.searchParams.get('api_key') ||
                scriptUrl.searchParams.get('apikey') ||
                scriptUrl.searchParams.get('key') ||
                '';

            const customServerUrl = scriptUrl.searchParams.get('server_url');
            if (customServerUrl) {
                serverUrl = customServerUrl.replace(/\/+$/, '');
            }
        } catch (error) {
            console.error('[CLIP] Error leyendo parametros del script:', error);
        }
    }

    if (!apiKey) {
        console.error('[CLIP] No se encontro api_key en el script de Tiendanube.');
        return;
    }

    function waitForOverlay(onReady) {
        let attempts = 0;
        const maxAttempts = 60;

        const poll = setInterval(() => {
            attempts += 1;
            if (window.CLIPV2 && window.CLIPV2.overlay && typeof window.CLIPV2.overlay.open === 'function') {
                clearInterval(poll);
                onReady();
                return;
            }

            if (attempts >= maxAttempts) {
                clearInterval(poll);
                isLoadingWidget = false;
                console.error('[CLIP] No se pudo inicializar el modal en la tienda.');
            }
        }, 100);
    }

    function loadWidgetAndOpen() {
        if (window.CLIPV2 && window.CLIPV2.overlay && typeof window.CLIPV2.overlay.open === 'function') {
            window.CLIPV2.overlay.open();
            return;
        }

        if (isLoadingWidget) {
            return;
        }

        isLoadingWidget = true;

        window.CLIPWidget = window.CLIPWidget || {};
        window.CLIPWidget.apiKey = apiKey;
        window.CLIPWidget.serverUrl = serverUrl;

        const existingWidgetScript = Array.from(document.getElementsByTagName('script')).find((s) =>
            s.src && s.src.indexOf(WIDGET_SCRIPT_PATH) !== -1
        );

        if (existingWidgetScript) {
            waitForOverlay(() => {
                isLoadingWidget = false;
                window.CLIPV2.overlay.open();
            });
            return;
        }

        const widgetScript = document.createElement('script');
        widgetScript.src = `${serverUrl}${WIDGET_SCRIPT_PATH}`;
        widgetScript.async = true;
        widgetScript.onload = () => {
            waitForOverlay(() => {
                isLoadingWidget = false;
                window.CLIPV2.overlay.open();
            });
        };
        widgetScript.onerror = () => {
            isLoadingWidget = false;
            console.error('[CLIP] Error cargando el script del widget.');
        };

        document.head.appendChild(widgetScript);
    }

    // Crear estilos del boton
    const styles = `
        #clip-floating-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            cursor: pointer;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            border: none;
        }

        #clip-floating-button:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }

        #clip-floating-button svg {
            width: 30px;
            height: 30px;
            fill: white;
        }

        @media (max-width: 768px) {
            #clip-floating-button {
                width: 50px;
                height: 50px;
                bottom: 15px;
                right: 15px;
            }

            #clip-floating-button svg {
                width: 25px;
                height: 25px;
            }
        }
    `;

    // Inyectar estilos
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);

    // Crear boton flotante
    const button = document.createElement('button');
    button.id = 'clip-floating-button';
    button.setAttribute('aria-label', 'Busqueda con IA');
    button.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            <circle cx="9.5" cy="9.5" r="1.5"/>
        </svg>
    `;

    button.addEventListener('click', loadWidgetAndOpen);

    // Agregar al DOM cuando este listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            document.body.appendChild(button);
        });
    } else {
        document.body.appendChild(button);
    }
})();
