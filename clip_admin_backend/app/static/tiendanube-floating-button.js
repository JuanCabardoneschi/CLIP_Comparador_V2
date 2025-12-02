/**
 * CLIP Comparador - Botón Flotante para Tiendanube
 * Se inyecta automáticamente en todas las páginas de la tienda
 */
(function() {
    'use strict';

    // Evitar ejecución múltiple
    if (window.CLIP_BUTTON_LOADED) return;
    window.CLIP_BUTTON_LOADED = true;

    // Configuración
    const WIDGET_URL = 'https://clipcomparadorv2-production.up.railway.app/tiendanube/widget';

    // Crear estilos del botón
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

        #clip-modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000000;
            display: none;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s ease;
        }

        #clip-modal-overlay.active {
            display: flex;
        }

        #clip-modal-container {
            width: 90%;
            height: 90%;
            max-width: 1200px;
            background: white;
            border-radius: 20px;
            overflow: hidden;
            position: relative;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: slideUp 0.4s ease;
        }

        #clip-modal-close {
            position: absolute;
            top: 15px;
            right: 15px;
            width: 40px;
            height: 40px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 50%;
            border: none;
            cursor: pointer;
            z-index: 10;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }

        #clip-modal-close:hover {
            background: rgba(0, 0, 0, 0.8);
            transform: rotate(90deg);
        }

        #clip-modal-close svg {
            width: 20px;
            height: 20px;
            fill: white;
        }

        #clip-modal-iframe {
            width: 100%;
            height: 100%;
            border: none;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
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

            #clip-modal-container {
                width: 95%;
                height: 95%;
                border-radius: 10px;
            }
        }
    `;

    // Inyectar estilos
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);

    // Crear botón flotante
    const button = document.createElement('button');
    button.id = 'clip-floating-button';
    button.setAttribute('aria-label', 'Búsqueda con IA');
    button.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            <circle cx="9.5" cy="9.5" r="1.5"/>
        </svg>
    `;

    // Crear modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'clip-modal-overlay';

    const modalContainer = document.createElement('div');
    modalContainer.id = 'clip-modal-container';

    const closeButton = document.createElement('button');
    closeButton.id = 'clip-modal-close';
    closeButton.setAttribute('aria-label', 'Cerrar');
    closeButton.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
    `;

    const iframe = document.createElement('iframe');
    iframe.id = 'clip-modal-iframe';
    iframe.src = WIDGET_URL;
    iframe.setAttribute('allowfullscreen', '');

    modalContainer.appendChild(closeButton);
    modalContainer.appendChild(iframe);
    overlay.appendChild(modalContainer);

    // Event listeners
    button.addEventListener('click', () => {
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    const closeModal = () => {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    };

    closeButton.addEventListener('click', closeModal);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal();
        }
    });

    // Cerrar con ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay.classList.contains('active')) {
            closeModal();
        }
    });

    // Agregar al DOM cuando esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            document.body.appendChild(button);
            document.body.appendChild(overlay);
        });
    } else {
        document.body.appendChild(button);
        document.body.appendChild(overlay);
    }
})();
