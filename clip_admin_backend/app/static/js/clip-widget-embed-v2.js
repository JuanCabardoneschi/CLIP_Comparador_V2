/**
 * CLIP Widget V2 - Modern Tab Design
 * El cliente solo necesita:
 * <script>
 *   window.CLIPWidget = { apiKey: "YOUR_KEY", serverUrl: "https://..." };
 * </script>
 * <div id="clip-widget"></div>
 * <script src="/static/js/clip-widget-embed-v2.js"></script>
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
            }

            .clip-tab-content {
                display: none;
                padding: 2.5rem;
                animation: clipFadeIn 0.3s ease;
            }

            .clip-tab-content.active {
                display: block;
            }

            @keyframes clipFadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
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
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
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
            }

            .clip-examples {
                display: flex;
                flex-wrap: wrap;
                gap: 0.75rem;
                margin-top: 1.5rem;
            }

            .clip-examples-label {
                width: 100%;
                color: #64748b;
                font-size: 0.9rem;
                margin-bottom: 0.5rem;
            }

            .clip-example-tag {
                background: #f1f5f9;
                color: #475569;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.2s;
                border: 2px solid transparent;
            }

            .clip-example-tag:hover {
                background: #e0e7ff;
                color: #667eea;
                border-color: #c7d2fe;
            }

            /* Loading */
            .clip-loading {
                display: none;
                text-align: center;
                padding: 3rem;
            }

            .clip-loading.active {
                display: block;
            }

            .clip-spinner {
                border: 4px solid #f3f4f6;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 60px; height: 60px;
                animation: clipSpin 1s linear infinite;
                margin: 0 auto 1rem;
            }

            @keyframes clipSpin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .clip-loading-text {
                color: #64748b;
                font-size: 1.1rem;
            }

            /* Error */
            .clip-error {
                display: none;
                background: #fee2e2;
                color: #991b1b;
                padding: 1rem;
                border-radius: 8px;
                margin-top: 1rem;
            }

            .clip-error.active {
                display: block;
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

            .clip-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 1.5rem;
            }

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
        `;
        document.head.appendChild(style);

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
                        <span class="clip-tab-icon">📸</span>
                        <span>Búsqueda Visual</span>
                    </button>
                    <button class="clip-tab" data-tab="text">
                        <span class="clip-tab-icon">💬</span>
                        <span>Búsqueda por Descripción</span>
                    </button>
                </div>

                <div class="clip-tab-content active" id="clip-visual-tab">
                    <h2 class="clip-search-title">Encuentra productos con una foto</h2>
                    <p class="clip-search-subtitle">Sube una imagen y encontraremos productos similares</p>

                    <div class="clip-upload-area" id="clip-upload">
                        <div class="clip-upload-icon">📷</div>
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
                </div>

                <div class="clip-tab-content" id="clip-text-tab">
                    <div class="clip-text-content">
                        <h2 class="clip-search-title">Busca por descripción</h2>
                        <p class="clip-search-subtitle">Describe lo que buscas y encuentra productos que coincidan</p>

                        <div class="clip-input-wrap">
                            <span class="clip-input-icon">🔍</span>
                            <input type="text" class="clip-input" id="clip-text-input"
                                   placeholder="Ej: camisa blanca, delantal marrón, camisa casual...">
                        </div>
                        <button class="clip-search-btn" id="clip-text-search-btn">Buscar productos</button>

                        <div class="clip-examples">
                            <div class="clip-examples-label">💡 Ejemplos populares:</div>
                            <span class="clip-example-tag" data-query="delantal azul">delantal azul</span>
                            <span class="clip-example-tag" data-query="camisa clara">camisa clara</span>
                            <span class="clip-example-tag" data-query="delantal marrón">delantal marrón</span>
                            <span class="clip-example-tag" data-query="camisa casual">camisa casual</span>
                            <span class="clip-example-tag" data-query="delantal negro">delantal negro</span>
                        </div>
                    </div>
                </div>

                <div class="clip-loading" id="clip-loading">
                    <div class="clip-spinner"></div>
                    <div class="clip-loading-text">Analizando con inteligencia artificial...</div>
                </div>

                <div class="clip-error" id="clip-error"></div>

                <div class="clip-results" id="clip-results">
                    <div class="clip-results-header">
                        <h2 class="clip-results-title">✨ Productos Encontrados</h2>
                        <div class="clip-results-count" id="clip-results-count"></div>
                    </div>
                    <div class="clip-grid" id="clip-grid"></div>
                </div>
            </div>
        `;

        // State
        let selectedFile = null;

        // Tab switching
        container.querySelectorAll('.clip-tab').forEach(tab => {
            tab.addEventListener('click', function() {
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

        upload.addEventListener('click', () => fileInput.click());

        upload.addEventListener('dragover', (e) => {
            e.preventDefault();
            upload.classList.add('drag-over');
        });

        upload.addEventListener('dragleave', () => {
            upload.classList.remove('drag-over');
        });

        upload.addEventListener('drop', (e) => {
            e.preventDefault();
            upload.classList.remove('drag-over');
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
            selectedFile = null;
            preview.classList.remove('active');
            upload.style.display = 'block';
            fileInput.value = '';
        });

        visualSearchBtn.addEventListener('click', () => {
            if (!selectedFile) return;
            performVisualSearch(selectedFile);
        });

        // Text search
        const textInput = container.querySelector('#clip-text-input');
        const textSearchBtn = container.querySelector('#clip-text-search-btn');

        textSearchBtn.addEventListener('click', () => {
            const query = textInput.value.trim();
            if (!query) {
                alert('Por favor ingresa una descripción');
                return;
            }
            performTextSearch(query);
        });

        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') textSearchBtn.click();
        });

        // Example tags
        container.querySelectorAll('.clip-example-tag').forEach(tag => {
            tag.addEventListener('click', function() {
                const query = this.dataset.query;
                textInput.value = query;
                textSearchBtn.click();
            });
        });

        // Visual search API
        function performVisualSearch(file) {
            const formData = new FormData();
            formData.append('image', file);

            showLoading();

            fetch(`${config.serverUrl}/api/search`, {
                method: 'POST',
                headers: { 'X-API-Key': config.apiKey },
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                hideLoading();
                if (data.success && data.results && data.results.length > 0) {
                    displayResults(data.results, data.total_results);
                } else {
                    showError(data.error || 'No se encontraron productos similares');
                }
            })
            .catch(err => {
                hideLoading();
                showError('Error al realizar la búsqueda. Intenta nuevamente.');
                console.error(err);
            });
        }

        // Text search API
        function performTextSearch(query) {
            showLoading();

            fetch(`${config.serverUrl}/api/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': config.apiKey
                },
                body: JSON.stringify({ query, max_results: 20 })
            })
            .then(res => res.json())
            .then(data => {
                hideLoading();
                if (data.success && data.results && data.results.length > 0) {
                    displayResults(data.results, data.total_results);
                } else {
                    showError(data.error || 'No se encontraron productos');
                }
            })
            .catch(err => {
                hideLoading();
                showError('Error al realizar la búsqueda. Intenta nuevamente.');
                console.error(err);
            });
        }

        // Display results
        function displayResults(results, total) {
            const resultsDiv = container.querySelector('#clip-results');
            const countDiv = container.querySelector('#clip-results-count');
            const gridDiv = container.querySelector('#clip-grid');

            countDiv.textContent = `${total} producto${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}`;

            gridDiv.innerHTML = results.map(r => `
                <div class="clip-product">
                    <div class="clip-product-img-wrap">
                        <img src="${r.image_url}" alt="${r.name}" class="clip-product-img">
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
                    </div>
                </div>
            `).join('');

            resultsDiv.classList.add('active');
        }

        // Helpers
        function showLoading() {
            container.querySelector('#clip-loading').classList.add('active');
            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-error').classList.remove('active');
        }

        function hideLoading() {
            container.querySelector('#clip-loading').classList.remove('active');
        }

        function showError(msg) {
            const errorDiv = container.querySelector('#clip-error');
            errorDiv.textContent = msg;
            errorDiv.classList.add('active');
            container.querySelector('#clip-results').classList.remove('active');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
