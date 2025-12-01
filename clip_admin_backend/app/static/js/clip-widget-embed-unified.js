/**
 * CLIP Widget Unified - Best of V1 + V2 + Multi-Crop Backend
 *
 * Features:
 * ✅ Multi-category mode by default (multi_category: 'true')
 * ✅ Overlay de bloqueo por tab (previene doble submit)
 * ✅ isProcessing flag con guards
 * ✅ Refinement suggestions con chips interactivos
 * ✅ Display multi-categoría con secciones verticales
 * ✅ Error handling avanzado (category_not_detected)
 * ✅ Atributos dinámicos + URL producto
 * ✅ SVG icons (no emojis para evitar encoding issues)
 * ✅ Integrado con backend multi-crop (8 crops + region weights + pair exclusion)
 *
 * El cliente solo necesita:
 * <script>
 *   window.CLIPWidget = { apiKey: "YOUR_KEY", serverUrl: "https://..." };
 * </script>
 * <div id="clip-widget"></div>
 * <script src="/static/js/clip-widget-embed-unified.js"></script>
 */

(function() {
    'use strict';

    if (!window.CLIPWidget || !window.CLIPWidget.apiKey) {
        console.error('CLIP Widget: Se requiere window.CLIPWidget = { apiKey: "YOUR_KEY" }');
        return;
    }

    function initWidget() {
        const config = {
            apiKey: window.CLIPWidget.apiKey,
            serverUrl: window.CLIPWidget.serverUrl || 'https://clipcomparadorv2-production.up.railway.app',
            containerId: window.CLIPWidget.containerId || 'clip-widget'
        };

        // Inject CSS
        const style = document.createElement('style');
        style.textContent = `
            .clip-widget-wrap {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: white;
                border-radius: 16px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.06);
                overflow: hidden;
                max-width: 100%;
            }

            .clip-tabs {
                display: flex;
                border-bottom: 2px solid #f1f5f9;
                background: #fafbfc;
            }

            .clip-tab {
                flex: 1;
                padding: 1.5rem 2rem;
                background: transparent;
                border: none;
                cursor: pointer;
                font-size: 1.1rem;
                font-weight: 600;
                color: #64748b;
                transition: all 0.3s;
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.75rem;
            }

            .clip-tab:hover {
                background: #f8fafc;
                color: #475569;
            }

            .clip-tab.active {
                color: #667eea;
                background: white;
            }

            .clip-tab.active::after {
                content: '';
                position: absolute;
                bottom: -2px;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            }

            .clip-tab-icon {
                font-size: 1.5rem;
                display: flex;
                align-items: center;
            }

            .clip-tab-content {
                display: none;
                padding: 2.5rem;
                animation: clipFadeIn 0.3s ease;
                position: relative;
            }

            .clip-tab-content.active {
                display: block;
            }

            @keyframes clipFadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @keyframes slideDown {
                from { opacity: 0; transform: translate(-50%, -20px); }
                to { opacity: 1; transform: translate(-50%, 0); }
            }

            .clip-search-title {
                font-size: 1.8rem;
                color: #1e293b;
                margin-bottom: 0.5rem;
                font-weight: 700;
                text-align: center;
            }

            .clip-search-subtitle {
                color: #64748b;
                font-size: 1.05rem;
                margin-bottom: 2rem;
                text-align: center;
            }

            /* Visual Search */
            .clip-upload-area {
                border: 3px dashed #cbd5e1;
                border-radius: 16px;
                padding: 3rem 2rem;
                cursor: pointer;
                transition: all 0.3s ease;
                background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                position: relative;
                overflow: hidden;
                text-align: center;
            }

            .clip-upload-area::before {
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
                opacity: 0;
                transition: opacity 0.3s;
            }

            .clip-upload-area:hover::before,
            .clip-upload-area.drag-over::before {
                opacity: 1;
            }

            .clip-upload-area:hover {
                border-color: #667eea;
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
            }

            .clip-upload-area.drag-over {
                border-color: #667eea;
                background: #eef2ff;
                border-style: solid;
            }

            .clip-upload-icon {
                font-size: 4rem;
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #667eea;
            }

            .clip-upload-text {
                font-size: 1.2rem;
                color: #334155;
                margin-bottom: 0.5rem;
                font-weight: 600;
            }

            .clip-upload-hint {
                font-size: 1rem;
                color: #94a3b8;
            }

            .clip-preview {
                display: none;
                margin: 2rem auto;
                text-align: center;
            }

            .clip-preview.active {
                display: block;
            }

            .clip-preview-container {
                display: inline-block;
                position: relative;
            }

            .clip-preview img {
                max-width: 400px;
                max-height: 400px;
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.12);
                border: 4px solid white;
            }

            .clip-remove-btn {
                position: absolute;
                top: -12px; right: -12px;
                background: #ef4444;
                color: white;
                border: none;
                width: 36px; height: 36px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 1.2rem;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
                transition: transform 0.2s;
            }

            .clip-remove-btn:hover {
                transform: scale(1.1);
            }

            .clip-search-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 1rem 3rem;
                font-size: 1.1rem;
                border-radius: 12px;
                cursor: pointer;
                transition: all 0.3s;
                font-weight: 600;
                margin-top: 1.5rem;
                box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
            }

            .clip-search-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
            }

            .clip-search-btn:disabled {
                background: #cbd5e1;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }

            /* Text Search */
            .clip-text-content {
                max-width: 700px;
                margin: 0 auto;
            }

            .clip-input-wrap {
                position: relative;
                margin-bottom: 1rem;
            }

            .clip-input {
                width: 100%;
                padding: 1.25rem 1.5rem 1.25rem 3.5rem;
                font-size: 1.1rem;
                border: 2px solid #e5e7eb;
                border-radius: 16px;
                transition: all 0.3s;
                font-family: inherit;
                box-sizing: border-box;
            }

            .clip-input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
            }

            .clip-input-icon {
                position: absolute;
                left: 1.25rem;
                top: 50%;
                transform: translateY(-50%);
                font-size: 1.3rem;
                color: #94a3b8;
                display: flex;
                align-items: center;
            }

            /* Overlay de bloqueo durante procesamiento */
            .clip-overlay {
                position: absolute;
                inset: 0;
                background: rgba(255, 255, 255, 0.85);
                display: none;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                z-index: 20;
                backdrop-filter: blur(2px);
            }

            .clip-overlay.active {
                display: flex;
            }

            .clip-overlay .clip-spinner {
                border: 4px solid #f3f4f6;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 60px; height: 60px;
                animation: clipSpin 1s linear infinite;
            }

            @keyframes clipSpin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .clip-overlay .clip-loading-text {
                margin-top: 1rem;
                color: #475569;
                font-weight: 600;
                font-size: 1.1rem;
            }

            /* Error */
            .clip-error {
                display: none;
                background: #fee2e2;
                color: #991b1b;
                padding: 1.25rem;
                border-radius: 12px;
                margin-top: 1.5rem;
            }

            .clip-error.active {
                display: block;
            }

            .clip-category-error {
                text-align: center;
            }

            .clip-error-icon {
                font-size: 3rem;
                margin-bottom: 1rem;
            }

            .clip-error-message {
                font-size: 1.1rem;
                font-weight: 600;
                margin-bottom: 1rem;
            }

            .clip-available-categories {
                margin-top: 1.5rem;
                padding: 1rem;
                background: rgba(255, 255, 255, 0.5);
                border-radius: 8px;
            }

            .clip-category-tag {
                display: inline-block;
                background: white;
                color: #991b1b;
                padding: 0.4rem 0.8rem;
                border-radius: 16px;
                margin: 0.25rem;
                font-size: 0.9rem;
                font-weight: 500;
                border: 1px solid #fca5a5;
            }

            /* Refinement Suggestions */
            .clip-refinement {
                background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                border: 2px solid #fbbf24;
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1.5rem 0;
                animation: clipFadeIn 0.3s ease;
                display: none;
            }

            .clip-refinement.active {
                display: block;
            }

            .clip-refinement-icon {
                font-size: 2rem;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .clip-refinement-message {
                font-size: 1.1rem;
                font-weight: 600;
                color: #78350f;
                margin-bottom: 1rem;
                text-align: center;
            }

            .clip-refinement-label {
                font-size: 0.9rem;
                color: #92400e;
                font-weight: 600;
                margin-bottom: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .clip-suggestions {
                display: flex;
                flex-wrap: wrap;
                gap: 0.75rem;
                margin-top: 0.5rem;
            }

            .clip-suggestion-chip {
                background: white;
                color: #1f2937;
                padding: 0.75rem 1.25rem;
                border-radius: 20px;
                border: 2px solid #fbbf24;
                cursor: pointer;
                transition: all 0.2s;
                font-weight: 500;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }

            .clip-suggestion-chip:hover {
                background: #667eea;
                color: white;
                border-color: #667eea;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }

            /* Results */
            .clip-results {
                display: none;
                margin-top: 2rem;
            }

            .clip-results.active {
                display: block;
            }

            .clip-results-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 1.5rem;
                flex-wrap: wrap;
                gap: 1rem;
            }

            .clip-results-title {
                font-size: 1.5rem;
                color: #1e293b;
                font-weight: 700;
            }

            .clip-results-count {
                color: #64748b;
                font-size: 1rem;
            }

            .clip-category-substitution {
                flex: 1 1 100%;
                background: #fff3cd;
                border: 1px solid #ffeeba;
                color: #856404;
                padding: 0.75rem 1rem;
                border-radius: 8px;
                font-size: 0.95rem;
                font-weight: 500;
                display: none;
            }

            .clip-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 1.5rem;
            }

            /* Multi-Category Sections (Vertical Layout) */
            .clip-grid:has(.clip-category-section) {
                display: block;
            }

            .clip-category-section {
                margin-bottom: 3rem;
                padding-bottom: 2rem;
                border-bottom: 2px solid #e5e7eb;
            }

            .clip-category-section:last-child {
                border-bottom: none;
                margin-bottom: 0;
                padding-bottom: 0;
            }

            .clip-category-header {
                margin-bottom: 1.5rem;
                padding: 1.25rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                color: white;
            }

            .clip-category-title {
                font-size: 1.5rem;
                font-weight: 700;
                margin: 0 0 0.5rem 0;
            }

            .clip-category-meta {
                display: flex;
                gap: 1.5rem;
                font-size: 0.9rem;
                opacity: 0.95;
                flex-wrap: wrap;
            }

            .clip-category-count {
                font-weight: 600;
            }

            .clip-category-confidence {
                opacity: 0.85;
            }

            .clip-category-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 1.5rem;
            }

            /* Product Cards */
            .clip-product {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                overflow: hidden;
                transition: transform 0.3s, box-shadow 0.3s;
                cursor: pointer;
            }

            .clip-product:hover {
                transform: translateY(-4px);
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);
            }

            .clip-product-img-wrap {
                position: relative;
                width: 100%;
                padding-top: 133%;
                background: #f9fafb;
                overflow: hidden;
            }

            .clip-product-img {
                position: absolute;
                top: 0; left: 0;
                width: 100%; height: 100%;
                object-fit: cover;
            }

            .clip-similarity-badge {
                position: absolute;
                top: 12px; right: 12px;
                background: rgba(16, 185, 129, 0.95);
                color: white;
                padding: 0.4rem 0.8rem;
                border-radius: 20px;
                font-weight: 600;
                font-size: 0.9rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }

            .clip-product-info {
                padding: 1.25rem;
            }

            .clip-product-category {
                color: #6b7280;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 0.5rem;
            }

            .clip-product-name {
                font-size: 1.05rem;
                font-weight: 600;
                color: #111827;
                margin-bottom: 0.75rem;
                line-height: 1.4;
            }

            .clip-product-price {
                font-size: 1.3rem;
                font-weight: 700;
                color: #000;
            }

            .clip-product-stock {
                font-size: 0.85rem;
                color: #64748b;
                margin-top: 0.5rem;
            }

            .clip-product-stock.in-stock {
                color: #10b981;
            }

            .clip-product-attributes {
                margin-top: 0.75rem;
                padding-top: 0.75rem;
                border-top: 1px solid #e5e7eb;
            }

            .clip-product-attribute {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                font-size: 0.85rem;
                margin-bottom: 0.4rem;
            }

            .clip-attr-label {
                color: #6b7280;
                font-weight: 500;
            }

            .clip-attr-value {
                color: #111827;
                text-align: right;
                flex: 1;
                margin-left: 0.5rem;
            }

            .clip-product-link {
                display: block;
                margin-top: 0.75rem;
                padding: 0.6rem 1rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 6px;
                text-align: center;
                font-size: 0.9rem;
                font-weight: 600;
                transition: transform 0.2s, box-shadow 0.2s;
            }

            .clip-product-link:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }

            /* Responsive */
            @media (max-width: 768px) {
                .clip-tab {
                    padding: 1rem 1.5rem;
                    font-size: 1rem;
                }

                .clip-tab-content {
                    padding: 1.5rem;
                }

                .clip-search-title {
                    font-size: 1.5rem;
                }

                .clip-grid,
                .clip-category-grid {
                    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                    gap: 1rem;
                }

                .clip-preview img {
                    max-width: 100%;
                    max-height: 300px;
                }
            }
        `;
        document.head.appendChild(style);

        // Iconos SVG inline
        const icons = {
            camera: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>',
            chat: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
            search: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>',
            bulb: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"></path></svg>',
            magnifier: '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>'
        };

        // HTML
        const container = document.getElementById(config.containerId);
        if (!container) {
            console.error(`CLIP Widget: Container #${config.containerId} not found`);
            return;
        }

        container.innerHTML = `
            <div class="clip-widget-wrap">
                <div class="clip-tabs">
                    <button class="clip-tab active" data-tab="visual">
                        <span class="clip-tab-icon">${icons.camera}</span>
                        <span>Búsqueda Visual</span>
                    </button>
                    <button class="clip-tab" data-tab="text">
                        <span class="clip-tab-icon">${icons.chat}</span>
                        <span>Búsqueda por Descripción</span>
                    </button>
                </div>

                <div class="clip-tab-content active" id="clip-visual-tab">
                    <h2 class="clip-search-title">Encuentra productos con una foto</h2>
                    <p class="clip-search-subtitle">Sube una imagen y encontraremos productos similares en múltiples categorías</p>

                    <div class="clip-upload-area" id="clip-upload">
                        <div class="clip-upload-icon">${icons.camera}</div>
                        <div class="clip-upload-text">Arrastra una imagen aquí</div>
                        <div class="clip-upload-hint">o haz clic para seleccionar</div>
                    </div>
                    <input type="file" id="clip-file-input" accept="image/*" style="display:none;">

                    <div class="clip-preview" id="clip-preview">
                        <div class="clip-preview-container">
                            <img id="clip-preview-img" src="" alt="Preview">
                            <button class="clip-remove-btn" id="clip-remove">×</button>
                        </div>
                        <button class="clip-search-btn" id="clip-visual-search-btn">Buscar productos similares</button>
                    </div>

                    <div class="clip-overlay" id="clip-visual-overlay">
                        <div class="clip-spinner"></div>
                        <div class="clip-loading-text">Analizando imagen con IA...</div>
                    </div>
                </div>

                <div class="clip-tab-content" id="clip-text-tab">
                    <div class="clip-text-content">
                        <h2 class="clip-search-title">Busca por descripción</h2>
                        <p class="clip-search-subtitle">Describe lo que buscas y encuentra productos que coincidan</p>

                        <div class="clip-input-wrap">
                            <span class="clip-input-icon">${icons.search}</span>
                            <input type="text" class="clip-input" id="clip-text-input"
                                   placeholder="Ej: camisa blanca, delantal azul, remera casual...">
                        </div>
                        <button class="clip-search-btn" id="clip-text-search-btn">Buscar productos</button>
                    </div>

                    <div class="clip-overlay" id="clip-text-overlay">
                        <div class="clip-spinner"></div>
                        <div class="clip-loading-text">Buscando productos...</div>
                    </div>
                </div>

                <div class="clip-error" id="clip-error"></div>

                <div class="clip-refinement" id="clip-refinement">
                    <div class="clip-refinement-icon">${icons.bulb}</div>
                    <div class="clip-refinement-message" id="clip-refinement-message"></div>
                    <div id="clip-suggestions-container"></div>
                </div>

                <div class="clip-results" id="clip-results">
                    <div class="clip-results-header">
                        <h2 class="clip-results-title">✨ Productos Encontrados</h2>
                        <div class="clip-results-count" id="clip-results-count"></div>
                        <div class="clip-category-substitution" id="clip-category-substitution"></div>
                    </div>
                    <div class="clip-grid" id="clip-grid"></div>
                </div>
            </div>
        `;

        // State
        let selectedFile = null;
        let isProcessing = false;

        // Tab switching
        container.querySelectorAll('.clip-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                if (isProcessing) return; // No cambiar tabs durante procesamiento
                const targetTab = this.dataset.tab;
                container.querySelectorAll('.clip-tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                container.querySelectorAll('.clip-tab-content').forEach(c => c.classList.remove('active'));
                container.querySelector(`#clip-${targetTab}-tab`).classList.add('active');
            });
        });

        // Visual search upload
        const upload = container.querySelector('#clip-upload');
        const fileInput = container.querySelector('#clip-file-input');
        const preview = container.querySelector('#clip-preview');
        const previewImg = container.querySelector('#clip-preview-img');
        const removeBtn = container.querySelector('#clip-remove');
        const visualSearchBtn = container.querySelector('#clip-visual-search-btn');

        upload.addEventListener('click', () => {
            if (!isProcessing) fileInput.click();
        });

        upload.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!isProcessing) upload.classList.add('drag-over');
        });

        upload.addEventListener('dragleave', () => {
            upload.classList.remove('drag-over');
        });

        upload.addEventListener('drop', (e) => {
            e.preventDefault();
            upload.classList.remove('drag-over');
            if (isProcessing) return;
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                handleFile(file);
            }
        });

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) handleFile(file);
        });

        function handleFile(file) {
            selectedFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                upload.style.display = 'none';
                preview.classList.add('active');
            };
            reader.readAsDataURL(file);
        }

        removeBtn.addEventListener('click', () => {
            if (isProcessing) return;
            selectedFile = null;
            preview.classList.remove('active');
            upload.style.display = 'block';
            fileInput.value = '';
        });

        visualSearchBtn.addEventListener('click', () => {
            if (isProcessing) return;
            if (!selectedFile) return;
            performVisualSearch(selectedFile);
        });

        // Text search
        const textInput = container.querySelector('#clip-text-input');
        const textSearchBtn = container.querySelector('#clip-text-search-btn');

        textSearchBtn.addEventListener('click', () => {
            if (isProcessing) return;
            const query = textInput.value.trim();
            if (!query) {
                alert('Por favor ingresa una descripción');
                return;
            }
            performTextSearch(query);
        });

        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !isProcessing) textSearchBtn.click();
        });

        // Processing control
        function beginProcessing(scope) {
            isProcessing = true;

            if (scope === 'visual') {
                visualSearchBtn.disabled = true;
                fileInput.disabled = true;
                upload.style.pointerEvents = 'none';
                container.querySelector('#clip-visual-overlay').classList.add('active');
            } else if (scope === 'text') {
                textSearchBtn.disabled = true;
                textInput.disabled = true;
                container.querySelector('#clip-text-overlay').classList.add('active');
            }

            // Ocultar resultados previos
            container.querySelector('#clip-results').classList.remove('active');

                // 🔄 Normalización especial para respuesta GPT4V Unified (objeto results_by_category en formato mapa)
                if (data.success && data.results_by_category && !Array.isArray(data.results_by_category) && typeof data.results_by_category === 'object') {
                    console.log('🧪 Normalizando formato gpt4v-unified (mapa → arreglo)');
                    const prendas = (data.detection && Array.isArray(data.detection.prendas)) ? data.detection.prendas : [];
                    const confidenceMap = {};
                    prendas.forEach(p => {
                        if (p && p.categoria_sugerida) {
                            // usar confianza si viene, si no 0
                            confidenceMap[p.categoria_sugerida] = typeof p.confianza === 'number' ? p.confianza : 0;
                        }
                    });

                    const transformed = Object.entries(data.results_by_category).map(([categoryName, info]) => {
                        const rawProducts = Array.isArray(info.products) ? info.products : [];
                        // unificar campo similarity para el renderizador (usa similarity_score del endpoint nuevo)
                        const products = rawProducts.map(p => {
                            if (p && typeof p === 'object') {
                                return {
                                    ...p,
                                    similarity: typeof p.similarity === 'number' ? p.similarity : (typeof p.similarity_score === 'number' ? p.similarity_score : undefined)
                                };
                            }
                            return p;
                        });
                        return {
                            category_name: categoryName,
                            products,
                            product_count: info.results_returned || products.length || 0,
                            confidence: confidenceMap[categoryName] || 0
                        };
                    });

                    const totalProducts = (data.metadata && typeof data.metadata.total_products_found === 'number') ? data.metadata.total_products_found : transformed.reduce((acc, c) => acc + c.product_count, 0);

                    // Reutilizar render multi-categoría existente
                    if (transformed.length > 0) {
                        displayMultiCategoryResults(transformed, totalProducts, labelMap);
                        return; // salir para evitar rama legacy
                    }
                }
            container.querySelector('#clip-error').classList.remove('active');
            container.querySelector('#clip-refinement').classList.remove('active');
        }

        function endProcessing(scope) {
            isProcessing = false;

            if (scope === 'visual') {
                visualSearchBtn.disabled = false;
                fileInput.disabled = false;
                upload.style.pointerEvents = '';
                container.querySelector('#clip-visual-overlay').classList.remove('active');
            } else if (scope === 'text') {
                textSearchBtn.disabled = false;
                textInput.disabled = false;
                container.querySelector('#clip-text-overlay').classList.remove('active');
            }
        }

        // Visual search API
        function performVisualSearch(file) {
            if (isProcessing) return;
            beginProcessing('visual');

            const formData = new FormData();
            formData.append('image', file);
            formData.append('multi_category', 'true'); // ✅ MODO MULTI-CATEGORÍA

            // Usar endpoint unificado con GPT-4V (multi-categoría + base64 seguro)
            fetch(`${config.serverUrl}/api/search/gpt4v-unified`, {
                method: 'POST',
                headers: { 'X-API-Key': config.apiKey },
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                endProcessing('visual');

                console.log('🎯 API Response:', data);

                // Extraer labelMap del response
                const labelMap = data.exposed_attribute_labels || {};

                // Modo multi-categoría
                if (data.mode === 'multi_category' && data.results_by_category) {
                    displayMultiCategoryResults(data.results_by_category, data.total_results, labelMap);
                }
                // Fallback single categoría
                else if (data.success && data.results && data.results.length > 0) {
                    displayResults(data.results, data.total_results, labelMap);
                }
                // Error específico: categoría no detectada
                else if (data.error === 'category_not_detected') {
                    showCategoryNotDetectedError(data.message, data.details, data.available_categories);
                }
                else {
                    showError(data.error || 'No se encontraron productos similares');
                }
            })
            .catch(err => {
                endProcessing('visual');
                showError('Error al realizar la búsqueda. Por favor intenta nuevamente.');
                console.error('❌ Search error:', err);
            });
        }

        // Text search API con clasificación previa
        async function performTextSearch(query) {
            if (isProcessing) return;

            try {
                // Paso 1: Clasificar la query (fast endpoint sin costo)
                const classifyUrl = `${config.serverUrl}/api/search/classify?q=${encodeURIComponent(query)}`;
                const classifyResp = await fetch(classifyUrl, {
                    headers: { 'X-API-Key': config.apiKey }
                });
                const classification = await classifyResp.json();

                console.log('🔍 Query clasificada:', classification);

                // Paso 2: Si es compleja, mostrar banner antes de comenzar procesamiento
                let complexBanner = null;
                if (classification.success && classification.classification === 'complex') {
                    complexBanner = showComplexQueryBanner();
                }

                // Paso 3: Iniciar procesamiento real
                beginProcessing('text');

                const searchResp = await fetch(`${config.serverUrl}/api/search/text`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': config.apiKey
                    },
                    body: JSON.stringify({ query })
                });

                const data = await searchResp.json();

                // Ocultar banner si existía
                if (complexBanner) {
                    complexBanner.remove();
                }

                endProcessing('text');

                console.log('🎯 API Response:', data);

                // 📊 Log del modo de procesamiento (fast vs full)
                if (data.processing_mode) {
                    const modeEmoji = data.processing_mode === 'fast' ? '⚡' : '🔄';
                    console.log(`${modeEmoji} Modo de procesamiento: ${data.processing_mode.toUpperCase()}`);
                    if (data.processing_time) {
                        console.log(`⏱️ Tiempo total: ${data.processing_time}s`);
                    }
                }

                // Refinement suggestions
                if (data.needs_refinement) {
                    showRefinementSuggestions(data);
                    return;
                }

                if (data.success && data.results && data.results.length > 0) {
                    // Extraer labelMap del response
                    const labelMap = data.exposed_attribute_labels || {};

                    // Mostrar mensaje de sustitución de categoría si aplica
                    const subsDiv = container.querySelector('#clip-category-substitution');
                    if (subsDiv) {
                        if (data.category_substitution_info) {
                            const info = data.category_substitution_info;
                            const simText = (typeof info.similarity === 'number') ? ` (similitud ${info.similarity})` : '';
                            subsDiv.textContent = `La categoría más cercana a '${info.requested_text}' es '${info.matched_category}'${simText}.`;
                            subsDiv.style.display = 'block';
                        } else {
                            subsDiv.style.display = 'none';
                        }
                    }
                    displayResults(data.results, data.total_results, labelMap);
                } else if (data.error === 'category_not_detected') {
                    showCategoryNotDetectedError(data.message, data.details, data.available_categories);
                } else {
                    showError(data.error || 'No se encontraron productos');
                }
            } catch (err) {
                endProcessing('text');
                showError('Error al realizar la búsqueda. Por favor intenta nuevamente.');
                console.error('❌ Search error:', err);
            }
        }

        // Mostrar banner para consultas complejas
        function showComplexQueryBanner() {
            const banner = document.createElement('div');
            banner.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 1rem 2rem;
                border-radius: 12px;
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
                z-index: 10000;
                font-size: 1rem;
                font-weight: 600;
                animation: slideDown 0.3s ease-out;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            `;
            banner.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>Analizando tu consulta, esto puede tardar unos segundos...</span>
            `;
            document.body.appendChild(banner);
            return banner;
        }

        // Display multi-category results
        function displayMultiCategoryResults(resultsByCategory, totalResults, labelMap = {}) {
            const resultsDiv = container.querySelector('#clip-results');
            const countDiv = container.querySelector('#clip-results-count');
            const gridDiv = container.querySelector('#clip-grid');

            const totalProductCount = resultsByCategory.reduce((sum, cat) => sum + cat.product_count, 0);
            const totalCategories = resultsByCategory.length;
            countDiv.textContent = `${totalProductCount} productos en ${totalCategories} categoría${totalCategories !== 1 ? 's' : ''}`;

            console.log(`✨ Mostrando ${totalCategories} categorías con ${totalProductCount} productos totales`);

            let sectionsHtml = '';

            resultsByCategory.forEach((categoryData) => {
                const categoryName = categoryData.category_name;
                const products = categoryData.products;
                const confidence = Math.round(categoryData.confidence * 100);
                const productCount = products.length;

                sectionsHtml += `
                    <div class="clip-category-section">
                        <div class="clip-category-header">
                            <h3 class="clip-category-title">${categoryName}</h3>
                            <div class="clip-category-meta">
                                <span class="clip-category-count">${productCount} producto${productCount !== 1 ? 's' : ''}</span>
                                <span class="clip-category-confidence">${confidence}% de confianza</span>
                            </div>
                        </div>
                        <div class="clip-category-grid">
                            ${products.map(r => renderProductCard(r, labelMap)).join('')}
                        </div>
                    </div>
                `;
            });

            gridDiv.innerHTML = sectionsHtml;
            resultsDiv.classList.add('active');
        }

        // Display single category results
        function displayResults(results, total, labelMap = {}) {
            const resultsDiv = container.querySelector('#clip-results');
            const countDiv = container.querySelector('#clip-results-count');
            const gridDiv = container.querySelector('#clip-grid');

            countDiv.textContent = `${total} producto${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`;

            gridDiv.innerHTML = results.map(r => renderProductCard(r, labelMap)).join('');
            resultsDiv.classList.add('active');
        }

        // Render product card (shared)
        function renderProductCard(r, labelMap = {}) {
            // Atributos dinámicos
            let attributesHtml = '';
            if (r.attributes && typeof r.attributes === 'object') {
                const visibleAttrs = Object.entries(r.attributes)
                    .filter(([key, value]) => {
                        if (key === 'url_producto') return false;
                        return value !== null && value !== undefined && value !== '';
                    })
                    .map(([key, value]) => {
                        // 🏷️ Usar label del backend si existe, sino formatear el key
                        const keyLower = key.toLowerCase();
                        const label = labelMap[keyLower] || (key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1));
                        const displayValue = Array.isArray(value) ? value.join(', ') : value;
                        return `
                            <div class="clip-product-attribute">
                                <span class="clip-attr-label">${label}:</span>
                                <span class="clip-attr-value">${displayValue}</span>
                            </div>
                        `;
                    })
                    .join('');

                if (visibleAttrs) {
                    attributesHtml = `<div class="clip-product-attributes">${visibleAttrs}</div>`;
                }
            }

            // URL del producto
            const productUrl = r.product_url || (r.attributes && r.attributes.url_producto);
            const urlButtonHtml = productUrl ? `
                <a href="${productUrl}" target="_blank" class="clip-product-link">
                    Ver Producto →
                </a>
            ` : '';

            return `
                <div class="clip-product">
                    <div class="clip-product-img-wrap">
                        <img src="${r.image_url}" alt="${r.name}" class="clip-product-img" loading="lazy">
                        ${r.similarity ? `<div class="clip-similarity-badge">${Math.round(r.similarity * 100)}%</div>` : ''}
                    </div>
                    <div class="clip-product-info">
                        <div class="clip-product-category">${r.category || 'Producto'}</div>
                        <div class="clip-product-name">${r.name}</div>
                        <div class="clip-product-price">$${r.price ? r.price.toFixed(2) : 'N/A'}</div>
                        ${r.stock !== undefined ? `
                            <div class="clip-product-stock ${r.stock > 0 ? 'in-stock' : ''}">
                                ${r.stock > 0 ? `✓ Stock: ${r.stock}` : '✗ Sin stock'}
                            </div>
                        ` : ''}
                        ${attributesHtml}
                        ${urlButtonHtml}
                    </div>
                </div>
            `;
        }

        // Show refinement suggestions
        function showRefinementSuggestions(data) {
            const refinementDiv = container.querySelector('#clip-refinement');
            const messageDiv = container.querySelector('#clip-refinement-message');
            const suggestionsContainer = container.querySelector('#clip-suggestions-container');

            messageDiv.textContent = data.refinement_message || 'Tu búsqueda es muy general. ¿Podrías ser más específico?';

            let suggestionsHTML = '';

            if (data.suggestions && data.suggestions.colores && data.suggestions.colores.length > 0) {
                suggestionsHTML += `
                    <div class="clip-refinement-label">Colores disponibles:</div>
                    <div class="clip-suggestions">
                        ${data.suggestions.colores.map(color =>
                            `<button class="clip-suggestion-chip" data-type="color" data-value="${color}">
                                ${color}
                            </button>`
                        ).join('')}
                    </div>
                `;
            }

            if (data.suggestions && data.suggestions.contextos && data.suggestions.contextos.length > 0) {
                suggestionsHTML += `
                    <div class="clip-refinement-label" style="margin-top: 1rem;">Estilos disponibles:</div>
                    <div class="clip-suggestions">
                        ${data.suggestions.contextos.map(contexto =>
                            `<button class="clip-suggestion-chip" data-type="contexto" data-value="${contexto}">
                                ${contexto}
                            </button>`
                        ).join('')}
                    </div>
                `;
            }

            suggestionsContainer.innerHTML = suggestionsHTML;
            refinementDiv.classList.add('active');

            // Event listeners para chips
            suggestionsContainer.querySelectorAll('.clip-suggestion-chip').forEach(chip => {
                chip.addEventListener('click', function() {
                    const value = this.dataset.value;
                    const currentQuery = textInput.value;
                    const baseQuery = currentQuery.replace(/\b(de\s+)?colores?\b/gi, '').trim();
                    const newQuery = `${baseQuery} ${value}`.trim();

                    textInput.value = newQuery;
                    performTextSearch(newQuery);
                });
            });

            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-error').classList.remove('active');
        }

        // Show category not detected error
        function showCategoryNotDetectedError(message, details, categories) {
            const errorDiv = container.querySelector('#clip-error');
            const categoriesList = categories && categories.length > 0
                ? `<div class="clip-available-categories">
                     <strong>${details}</strong><br><br>
                     ${categories.map(cat => `<span class="clip-category-tag">${cat}</span>`).join('')}
                   </div>`
                : '';

            errorDiv.innerHTML = `
                <div class="clip-category-error">
                    <div class="clip-error-icon">${icons.magnifier}</div>
                    <div class="clip-error-message">${message}</div>
                    ${categoriesList}
                </div>
            `;
            errorDiv.classList.add('active');
            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-refinement').classList.remove('active');
        }

        // Show generic error
        function showError(msg) {
            const errorDiv = container.querySelector('#clip-error');
            errorDiv.innerHTML = `<div class="clip-error-message">${msg}</div>`;
            errorDiv.classList.add('active');
            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-refinement').classList.remove('active');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
