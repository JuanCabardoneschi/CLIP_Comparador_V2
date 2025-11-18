/**
 * CLIP Widget V3 - GPT-4 Vision Integration
 * Flujo: Imagen → GPT-4V detecta categorías → Búsqueda CLIP → Resultados agrupados
 *
 * Uso:
 * <script>
 *   window.CLIPWidget = { apiKey: "YOUR_KEY", serverUrl: "https://..." };
 * </script>
 * <div id="clip-widget"></div>
 * <script src="/static/js/clip-widget-embed-v3.js"></script>
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

            .clip-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2.5rem 2rem;
                text-align: center;
                color: white;
            }

            .clip-header h2 {
                margin: 0 0 0.5rem 0;
                font-size: 1.8rem;
                font-weight: 700;
            }

            .clip-header p {
                margin: 0;
                font-size: 1.1rem;
                opacity: 0.95;
            }

            /* Tabs */
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

            /* Upload Area */
            .clip-upload-area {
                border: 3px dashed #cbd5e1;
                border-radius: 16px;
                padding: 3rem 2rem;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
                background: #f8fafc;
            }

            .clip-upload-area:hover {
                border-color: #667eea;
                background: #f1f5f9;
            }

            .clip-upload-area.dragover {
                border-color: #667eea;
                background: #eef2ff;
                transform: scale(1.02);
            }

            .clip-upload-icon {
                font-size: 4rem;
                margin-bottom: 1rem;
            }

            .clip-upload-text {
                font-size: 1.2rem;
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 0.5rem;
            }

            .clip-upload-hint {
                font-size: 0.95rem;
                color: #64748b;
            }

            /* Preview */
            .clip-preview {
                display: none;
                margin-bottom: 2rem;
            }

            .clip-preview.active {
                display: block;
                animation: clipFadeIn 0.3s ease;
            }

            @keyframes clipFadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .clip-preview-container {
                position: relative;
                max-width: 400px;
                margin: 0 auto;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 16px rgba(0,0,0,0.1);
            }

            .clip-preview-img {
                width: 100%;
                display: block;
            }

            .clip-remove-btn {
                position: absolute;
                top: 12px; right: 12px;
                background: #ef4444;
                color: white;
                border: none;
                width: 40px; height: 40px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 1.3rem;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
                transition: all 0.2s;
                z-index: 10;
            }

            .clip-remove-btn:hover {
                transform: scale(1.15);
                background: #dc2626;
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
                width: 100%;
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

            /* Text Search Input */
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

            /* Loading */
            .clip-loading {
                display: none;
                text-align: center;
                padding: 3rem 2rem;
            }

            .clip-loading.active {
                display: block;
            }

            .clip-spinner {
                border: 4px solid #f3f4f6;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: clipSpin 1s linear infinite;
                margin: 0 auto 1.5rem;
            }

            @keyframes clipSpin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .clip-loading-text {
                font-size: 1.1rem;
                color: #64748b;
            }

            .clip-loading-steps {
                margin-top: 1rem;
                font-size: 0.9rem;
                color: #94a3b8;
            }

            /* Detection Results */
            .clip-detection {
                display: none;
                margin-bottom: 2rem;
                padding: 1.5rem;
                background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                border-radius: 12px;
            }

            .clip-detection.active {
                display: block;
                animation: clipFadeIn 0.3s ease;
            }

            .clip-detection-title {
                font-size: 1.1rem;
                font-weight: 600;
                color: #78350f;
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .clip-detection-items {
                display: flex;
                flex-wrap: wrap;
                gap: 0.75rem;
            }

            .clip-detection-tag {
                background: white;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-size: 0.9rem;
                color: #78350f;
                border: 2px solid #fbbf24;
                font-weight: 600;
            }

            .clip-detection-cost {
                margin-top: 1rem;
                font-size: 0.85rem;
                color: #92400e;
                text-align: right;
            }

            .clip-user-intent {
                margin-top: 1rem;
                padding: 1rem;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 8px;
                font-size: 0.95rem;
                color: #78350f;
                line-height: 1.6;
                border-left: 4px solid #fbbf24;
            }

            .clip-results {
                margin-top: 2rem;
            }

            /* Results */
            .clip-results {
                display: none;
            }

            .clip-results.active {
                display: block;
                animation: clipFadeIn 0.3s ease;
            }

            .clip-category-section {
                margin-bottom: 3rem;
            }

            .clip-category-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1rem 1.5rem;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 12px;
                margin-bottom: 1.5rem;
            }

            .clip-category-name {
                font-size: 1.3rem;
                font-weight: 700;
            }

            .clip-category-count {
                font-size: 0.95rem;
                opacity: 0.9;
            }

            .clip-product-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 1.5rem;
            }

            .clip-product {
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                transition: all 0.3s;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                height: 100%;
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
                display: flex;
                flex-direction: column;
                flex: 1;
            }

            .clip-product-name {
                font-size: 1.05rem;
                font-weight: 600;
                color: #111827;
                margin-bottom: 0.75rem;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                line-height: 1.25em;
                min-height: 2.5em; /* 2 líneas reservadas */
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

            .clip-product-stock.out-stock {
                color: #ef4444;
            }

            .clip-divider {
                height: 1px;
                background: #e5e7eb;
                margin: 8px 0 6px 0;
                border: 0;
            }

            /* Error */
            .clip-error {
                display: none;
                padding: 1.5rem;
                background: #fee2e2;
                border-left: 4px solid #ef4444;
                border-radius: 8px;
                color: #991b1b;
                margin-bottom: 1.5rem;
            }

            .clip-error.active {
                display: block;
                animation: clipFadeIn 0.3s ease;
            }

            /* No Results */
            .clip-no-results {
                text-align: center;
                padding: 3rem 2rem;
                color: #64748b;
            }

            .clip-no-results-icon {
                font-size: 4rem;
                margin-bottom: 1rem;
            }

            .clip-no-results-text {
                font-size: 1.2rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }

            .clip-no-results-hint {
                font-size: 0.95rem;
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
                <div class="clip-header">
                    <h2>🤖 Búsqueda Inteligente</h2>
                    <p>Encuentra productos similares con IA</p>
                </div>

                <!-- Tabs -->
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

                <!-- Tab Content: Visual Search -->
                <div class="clip-tab-content active" id="clip-visual-tab">
                    <h2 class="clip-search-title">Encuentra productos con una foto</h2>
                    <p class="clip-search-subtitle">Sube una imagen y encontraremos productos similares</p>

                    <div class="clip-upload-area" id="clip-upload">
                        <div class="clip-upload-icon">📸</div>
                        <div class="clip-upload-text">Arrastra una imagen aquí</div>
                        <div class="clip-upload-hint">o haz clic para seleccionar</div>
                    </div>
                    <input type="file" id="clip-file-input" accept="image/*" style="display:none;">

                    <div class="clip-preview" id="clip-preview">
                        <div class="clip-preview-container">
                            <img id="clip-preview-img" class="clip-preview-img" alt="Preview">
                            <button class="clip-remove-btn" id="clip-remove-btn">✕</button>
                        </div>
                        <button class="clip-search-btn" id="clip-visual-search-btn">
                            🔍 Buscar Productos Similares
                        </button>
                    </div>
                </div>

                <!-- Tab Content: Text Search -->
                <div class="clip-tab-content" id="clip-text-tab">
                    <h2 class="clip-search-title">Busca por descripción</h2>
                    <p class="clip-search-subtitle">Describe lo que buscas y encuentra productos que coincidan</p>

                    <div class="clip-input-wrap">
                        <span class="clip-input-icon">🔍</span>
                        <input type="text" class="clip-input" id="clip-text-input"
                               placeholder="Ej: camisa blanca, remera azul, pantalón negro...">
                    </div>
                    <button class="clip-search-btn" id="clip-text-search-btn">Buscar productos</button>
                </div>

                <!-- Common sections -->
                <div class="clip-error" id="clip-error"></div>

                <div class="clip-loading" id="clip-loading">
                    <div class="clip-spinner"></div>
                    <div class="clip-loading-text" id="clip-loading-text">Analizando...</div>
                    <div class="clip-loading-steps" id="clip-loading-steps">
                        <div>⏳ Detectando categorías con GPT-4 Vision</div>
                        <div>⏳ Buscando productos similares</div>
                    </div>
                </div>

                <div class="clip-detection" id="clip-detection">
                    <div class="clip-detection-title">
                        <span>🎯 Categorías Detectadas</span>
                    </div>
                    <div class="clip-detection-items" id="clip-detection-items"></div>
                    <div class="clip-detection-cost" id="clip-detection-cost"></div>
                </div>

                <div class="clip-results" id="clip-results"></div>
            </div>
        `;

        // Event Handlers
        let selectedFile = null;

        const upload = container.querySelector('#clip-upload');
        const fileInput = container.querySelector('#clip-file-input');
        const preview = container.querySelector('#clip-preview');
        const previewImg = container.querySelector('#clip-preview-img');
        const removeBtn = container.querySelector('#clip-remove-btn');
        const visualSearchBtn = container.querySelector('#clip-visual-search-btn');
        const textSearchBtn = container.querySelector('#clip-text-search-btn');
        const textInput = container.querySelector('#clip-text-input');

        // Tab switching
        const tabs = container.querySelectorAll('.clip-tab');
        const tabContents = container.querySelectorAll('.clip-tab-content');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;

                // Update active states
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(tc => tc.classList.remove('active'));

                tab.classList.add('active');
                container.querySelector(`#clip-${tabName}-tab`).classList.add('active');

                // Clear results when switching tabs
                clearResults();
            });
        });

        // Clear results helper
        function clearResults() {
            container.querySelector('#clip-detection').classList.remove('active');
            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-error').classList.remove('active');
            container.querySelector('#clip-loading').classList.remove('active');
        }

        // Upload area click
        upload.addEventListener('click', () => fileInput.click());

        // Drag & drop
        upload.addEventListener('dragover', (e) => {
            e.preventDefault();
            upload.classList.add('dragover');
        });

        upload.addEventListener('dragleave', () => {
            upload.classList.remove('dragover');
        });

        upload.addEventListener('drop', (e) => {
            e.preventDefault();
            upload.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                handleFile(file);
            }
        });

        // File input change
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
            clearResults();
        });

        // Visual search button
        visualSearchBtn.addEventListener('click', () => {
            if (!selectedFile) return;
            performGPT4VSearch(selectedFile);
        });

        // Text search button
        textSearchBtn.addEventListener('click', () => {
            const query = textInput.value.trim();
            if (!query) return;
            performTextSearch(query);
        });

        // Text input Enter key
        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = textInput.value.trim();
                if (query) performTextSearch(query);
            }
        });

        // API Call
        function performGPT4VSearch(file) {
            const formData = new FormData();
            formData.append('image', file);
            formData.append('max_results_per_category', '8');
            formData.append('similarity_threshold', '0.65');

            showLoading();

            // Usar siempre la API key actualizada de window.CLIPWidget
            const currentApiKey = window.CLIPWidget?.apiKey || config.apiKey;

            fetch(`${config.serverUrl}/api/search/gpt4v-unified`, {
                method: 'POST',
                headers: { 'X-API-Key': currentApiKey },
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                hideLoading();

                if (!data.success) {
                    showError(data.message || 'Error en la búsqueda');
                    return;
                }

                // Mostrar detección
                displayDetection(data.detection);

                // Mostrar resultados
                if (data.metadata.total_products_found > 0) {
                    displayResults(data.results_by_category, data.metadata);
                } else {
                    showNoResults();
                }
            })
            .catch(err => {
                hideLoading();
                showError('Error de conexión. Intenta nuevamente.');
                console.error(err);
            });
        }

        // Text Search API
        function performTextSearch(query) {
            showLoading();
            const loadingText = container.querySelector('#clip-loading-text');
            const loadingSteps = container.querySelector('#clip-loading-steps');

            // Cambiar texto de carga para búsqueda por texto
            if (loadingText) loadingText.textContent = 'Buscando productos...';
            if (loadingSteps) loadingSteps.style.display = 'none';

            const currentApiKey = window.CLIPWidget?.apiKey || config.apiKey;

            fetch(`${config.serverUrl}/api/search/text`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': currentApiKey
                },
                body: JSON.stringify({ query, limit: 20 })
            })
            .then(res => res.json())
            .then(data => {
                hideLoading();

                if (!data.success) {
                    showError(data.message || data.error || 'Error en la búsqueda');
                    return;
                }

                // La búsqueda por texto NO tiene detección GPT-4V, ocultar esa sección
                container.querySelector('#clip-detection').classList.remove('active');

                // Extraer atributos visibles del response
                const exposedKeys = data.exposed_attribute_keys || [];
                const labelMap = data.exposed_attribute_labels || {};

                // Mostrar resultados
                if (data.group_by_category && data.results_by_category) {
                    // ⭐ Resultados agrupados por categoría (categorías hermanas)
                    displayTextResultsByCategory(
                        data.results_by_category,
                        data.total_results || 0,
                        data.user_feedback || data.partial_match_info,
                        exposedKeys,
                        labelMap
                    );
                } else if (data.results && data.results.length > 0) {
                    // Resultados en lista plana (comportamiento original)
                    displayTextResults(
                        data.results,
                        data.total_results || data.results.length,
                        data.user_feedback || data.partial_match_info,
                        data.match_quality,
                        data.category_substitution_info,
                        exposedKeys,
                        labelMap
                    );
                } else {
                    // También propagar user_feedback cuando no hay resultados
                    showNoResults(data.user_feedback || data.partial_match_info);
                }
            })
            .catch(err => {
                hideLoading();
                showError('Error de conexión. Intenta nuevamente.');
                console.error(err);
            })
            .finally(() => {
                // Restaurar textos de loading para próxima búsqueda visual
                if (loadingText) loadingText.textContent = 'Analizando imagen con IA...';
                if (loadingSteps) loadingSteps.style.display = 'block';
            });
        }

        // ⭐ Display text search results AGRUPADOS POR CATEGORÍA (categorías hermanas)
        function displayTextResultsByCategory(resultsByCategory, total, partialMatchInfo, exposedKeys, labelMap) {
            exposedKeys = exposedKeys || [];
            labelMap = labelMap || {};
            const resultsDiv = container.querySelector('#clip-results');

            // Banner informativo global (si existe)
            const globalBannerHtml = partialMatchInfo ? `
                <div class="clip-partial-match-info" style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 16px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                ">
                    <div style="font-size: 15px; font-weight: 500; line-height: 1.5;">
                        ${partialMatchInfo.message}
                    </div>
                </div>
            ` : '';

            // Generar HTML por cada categoría
            const categorySections = Object.entries(resultsByCategory).map(([categoryName, products]) => {
                const renderProduct = (p) => `
                    <div class="clip-product">
                        <div class="clip-product-img-wrap">
                            <img src="${p.image_url}" alt="${p.name}" class="clip-product-img">
                            <div class="clip-similarity-badge">
                                ${Math.round((p.final_score || p.similarity || 0) * 100)}% Match
                            </div>
                        </div>
                        <div class="clip-product-info">
                            <div class="clip-product-name">${p.name}</div>
                            <div class="clip-product-price">
                                ${(p.price !== null && p.price !== undefined && typeof p.price === 'number') ? `$${p.price.toFixed(2)}` : 'Consultar'}
                            </div>
                            ${(() => {
                                const hasMatched = p.attributes_matched && Object.keys(p.attributes_matched).length > 0;
                                const hasRatio = typeof p.attributes_match_ratio === 'number' && p.attributes_match_ratio > 0;
                                const attrs = p.attributes || {};
                                const summary = Object.entries(attrs)
                                    .filter(([k]) => exposedKeys.length === 0 || exposedKeys.includes(String(k).toLowerCase()))
                                    .filter(([k]) => !p.attributes_matched || !(k in p.attributes_matched));
                                const fmt = (val) => {
                                    if (Array.isArray(val)) return val.join(', ');
                                    const raw = (val ?? '').toString();
                                    const n = raw.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
                                    if (n === 'si') return 'Sí';
                                    if (n === 'no') return 'No';
                                    return raw.toString();
                                };
                                let out = '';
                                const matchFmt = (val) => {
                                    const raw = (val ?? '').toString();
                                    const n = raw.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
                                    if (n === 'si') return 'Sí';
                                    if (n === 'no') return 'No';
                                    return raw;
                                };
                                if (hasMatched) {
                                    out += `<div class=\"clip-attr-badges\" style=\"margin-top:8px; display:flex; flex-wrap: wrap; gap:6px;\">` +
                                        Object.entries(p.attributes_matched).map(([k,v]) =>
                                            `<span style=\"background:#eef2ff;color:#374151;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid #e5e7eb;\">${labelMap[String(k).toLowerCase()] || k}: ${matchFmt(v)}</span>`
                                        ).join('') +
                                        `</div>`;
                                }
                                if (hasRatio) {
                                    out += `<div class=\"clip-divider\"></div>`;
                                    out += `<div style=\"width:100%; text-align:left; margin:6px 0;\">`+
                                        `<span style=\"background:#ecfdf5;color:#065f46;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:700;border:1px solid #d1fae5;\">${Math.round(p.attributes_match_ratio*100)}% atributos</span>`+
                                        `</div>`;
                                    out += `<div class=\"clip-divider\"></div>`;
                                } else if (hasMatched && summary.length) {
                                    out += `<div class=\"clip-divider\"></div>`;
                                }
                                if (summary.length) {
                                    out += `<div class=\"clip-attr-badges\" style=\"display:flex; flex-wrap: wrap; gap:6px;\">`+
                                        summary.map(([k,v]) =>
                                            `<span style=\"background:#f3f4f6;color:#374151;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid #e5e7eb;\">${labelMap[String(k).toLowerCase()] || k}: ${fmt(v)}</span>`
                                        ).join('')+
                                        `</div>`;
                                }
                                return out;
                            })()}
                            ${p.stock !== undefined ? `
                                <div class="clip-product-stock ${p.stock > 0 ? 'in-stock' : 'out-stock'}" style="margin-top:auto;">
                                    ${p.stock > 0 ? `✓ Stock: ${p.stock}` : '✗ Sin stock'}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;

                return `
                    <div class="clip-category-section">
                        <div class="clip-category-header">
                            <div class="clip-category-name">${categoryName}</div>
                            <div class="clip-category-count">${products.length} producto${products.length !== 1 ? 's' : ''}</div>
                        </div>
                        <div class="clip-product-grid">
                            ${products.map(renderProduct).join('')}
                        </div>
                    </div>
                `;
            }).join('');

            const html = `
                ${globalBannerHtml}
                ${categorySections}
            `;

            resultsDiv.innerHTML = html;
            resultsDiv.classList.add('active');
        }

        // Display text search results (sin agrupación por categoría)
        function displayTextResults(results, total, partialMatchInfo, matchQuality, categorySubstitutionInfo, exposedKeys, labelMap) {
            exposedKeys = exposedKeys || [];
            labelMap = labelMap || {};
            const resultsDiv = container.querySelector('#clip-results');

            // Mensaje contextual si hay partial match info
            const partialMatchHtml = partialMatchInfo ? `
                <div class="clip-partial-match-info" style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 16px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                ">
                    <div style="font-size: 15px; font-weight: 500; line-height: 1.5;">
                        ${partialMatchInfo.message}
                    </div>
                </div>
            ` : '';

            // Banner de sustitución de categoría si aplica
            const subsHtml = categorySubstitutionInfo ? `
                <div class="clip-category-substitution" style="
                    background: #fff3cd;
                    border: 1px solid #ffeeba;
                    color: #856404;
                    padding: 12px 14px;
                    border-radius: 10px;
                    margin-bottom: 16px;
                    font-size: 0.95rem;
                    font-weight: 500;
                ">
                    La categoría más cercana a '${categorySubstitutionInfo.requested_text}' es '${categorySubstitutionInfo.matched_category}'${typeof categorySubstitutionInfo.similarity === 'number' ? ` (similitud ${categorySubstitutionInfo.similarity})` : ''}.
                </div>
            ` : '';

            const html = `
                ${subsHtml}
                ${partialMatchHtml}
                <div class="clip-category-section">
                    <div class="clip-category-header">
                        <div class="clip-category-name">Resultados de Búsqueda</div>
                        <div class="clip-category-count">${total} producto${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''}</div>
                    </div>
                    <div class="clip-product-grid">
                        ${results.map(p => `
                            <div class="clip-product">
                                <div class="clip-product-img-wrap">
                                    <img src="${p.image_url}" alt="${p.name}" class="clip-product-img">
                                    <div class="clip-similarity-badge">
                                        ${Math.round((p.final_score || p.similarity || 0) * 100)}% Match
                                    </div>
                                </div>
                                <div class="clip-product-info">
                                    <div class="clip-product-name">${p.name}</div>
                                    <div class="clip-product-price">
                                        ${(p.price !== null && p.price !== undefined && typeof p.price === 'number') ? `$${p.price.toFixed(2)}` : 'Consultar'}
                                    </div>
                                    ${(() => {
                                        const hasMatched = p.attributes_matched && Object.keys(p.attributes_matched).length > 0;
                                        const hasRatio = typeof p.attributes_match_ratio === 'number' && p.attributes_match_ratio > 0;
                                        const attrs = p.attributes || {};
                                        const summary = Object.entries(attrs)
                                            .filter(([k]) => exposedKeys.length === 0 || exposedKeys.includes(String(k).toLowerCase()))
                                            .filter(([k]) => !p.attributes_matched || !(k in p.attributes_matched));
                                        const fmt = (val) => {
                                            if (Array.isArray(val)) return val.join(', ');
                                            const raw = (val ?? '').toString();
                                            const n = raw.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
                                            if (n === 'si') return 'Sí';
                                            if (n === 'no') return 'No';
                                            return raw.toString();
                                        };
                                        let out = '';
                                        const matchFmt = (val) => {
                                            const raw = (val ?? '').toString();
                                            const n = raw.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
                                            if (n === 'si') return 'Sí';
                                            if (n === 'no') return 'No';
                                            return raw;
                                        };
                                        if (hasMatched) {
                                            out += `<div class=\"clip-attr-badges\" style=\"margin-top:8px; display:flex; flex-wrap: wrap; gap:6px;\">` +
                                                Object.entries(p.attributes_matched).map(([k,v]) =>
                                                    `<span style=\"background:#eef2ff;color:#374151;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid #e5e7eb;\">${labelMap[String(k).toLowerCase()] || k}: ${matchFmt(v)}</span>`
                                                ).join('') +
                                                `</div>`;
                                        }
                                        if (hasRatio) {
                                            out += `<div class=\"clip-divider\"></div>`;
                                            out += `<div style=\"width:100%; text-align:left; margin:6px 0;\">`+
                                                `<span style=\"background:#ecfdf5;color:#065f46;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:700;border:1px solid #d1fae5;\">${Math.round(p.attributes_match_ratio*100)}% atributos</span>`+
                                                `</div>`;
                                            out += `<div class=\"clip-divider\"></div>`;
                                        } else if (hasMatched && summary.length) {
                                            out += `<div class=\"clip-divider\"></div>`;
                                        }
                                        if (summary.length) {
                                            out += `<div class=\"clip-attr-badges\" style=\"display:flex; flex-wrap: wrap; gap:6px;\">`+
                                                summary.map(([k,v]) =>
                                                    `<span style=\"background:#f3f4f6;color:#374151;padding:4px 8px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid #e5e7eb;\">${labelMap[String(k).toLowerCase()] || k}: ${fmt(v)}</span>`
                                                ).join('')+
                                                `</div>`;
                                        }
                                        return out;
                                    })()}
                                    ${p.stock !== undefined ? `
                                        <div class="clip-product-stock ${p.stock > 0 ? 'in-stock' : 'out-stock'}" style="margin-top:auto;">
                                            ${p.stock > 0 ? `✓ Stock: ${p.stock}` : '✗ Sin stock'}
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;

            resultsDiv.innerHTML = html;
            resultsDiv.classList.add('active');
        }

        // Display detection
        function displayDetection(detection) {
            const detectionDiv = container.querySelector('#clip-detection');
            const itemsDiv = container.querySelector('#clip-detection-items');
            const costDiv = container.querySelector('#clip-detection-cost');

            // Limpieza de render previo para evitar duplicados
            itemsDiv.innerHTML = '';
            costDiv.textContent = '';
            const existingIntent = detectionDiv.querySelector('.clip-user-intent');
            if (existingIntent) existingIntent.remove();

            const categories = detection.categories_detected_raw || detection.categories_detected || [];
            const userIntent = detection.user_intent || detection.mensaje_usuario || '';

            // Tags de categorías detectadas
            itemsDiv.innerHTML = categories.map(cat =>
                `<div class="clip-detection-tag">${cat}</div>`
            ).join('');

            // Intención del usuario (debajo de las categorías)
            if (userIntent) {
                const intentHtml = `
                    <div class="clip-user-intent">
                        <strong>💡 Intención detectada:</strong><br>
                        ${userIntent}
                    </div>
                `;
                costDiv.insertAdjacentHTML('beforebegin', intentHtml);
            }

            detectionDiv.classList.add('active');
        }

        // Display results
        function displayResults(resultsByCategory, metadata) {
            const resultsDiv = container.querySelector('#clip-results');

            const html = Object.entries(resultsByCategory).map(([categoryName, categoryData]) => {
                if (categoryData.products.length === 0) return '';

                return `
                    <div class="clip-category-section">
                        <div class="clip-category-header">
                            <div class="clip-category-name">${categoryName}</div>
                            <div class="clip-category-count">
                                ${categoryData.results_returned} de ${categoryData.total_in_category} productos
                            </div>
                        </div>
                        <div class="clip-product-grid">
                            ${categoryData.products.map(p => `
                                <div class="clip-product">
                                    <div class="clip-product-img-wrap">
                                        <img src="${p.image_url}" alt="${p.name}" class="clip-product-img">
                                        <div class="clip-similarity-badge">
                                            ${Math.round(p.similarity_score * 100)}% Match
                                        </div>
                                    </div>
                                    <div class="clip-product-info">
                                        <div class="clip-product-name">${p.name}</div>
                                        <div class="clip-product-price">
                                            ${p.price ? `$${p.price.toFixed(2)}` : 'Consultar'}
                                        </div>
                                        ${p.stock !== undefined ? `
                                            <div class="clip-product-stock ${p.stock > 0 ? 'in-stock' : 'out-stock'}" style="margin-top:auto;">
                                                ${p.stock > 0 ? `✓ Stock: ${p.stock}` : '✗ Sin stock'}
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }).join('');

            resultsDiv.innerHTML = html;
            resultsDiv.classList.add('active');
        }

        // No results
        function showNoResults(partialMatchInfo) {
            const resultsDiv = container.querySelector('#clip-results');

            const messageHtml = partialMatchInfo ? `
                <div class="clip-no-results-message" style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                ">
                    <div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">
                        ${partialMatchInfo.message}
                    </div>
                    ${partialMatchInfo.suggestion ? `
                        <div style="font-size: 14px; margin-top: 8px;">
                            ${partialMatchInfo.suggestion}
                        </div>
                    ` : ''}
                </div>
            ` : '';

            resultsDiv.innerHTML = `
                ${messageHtml}
                <div class="clip-no-results">
                    <div class="clip-no-results-icon">😔</div>
                    <div class="clip-no-results-text">${partialMatchInfo ? 'No hay coincidencias exactas' : 'No se encontraron productos similares'}</div>
                    <div class="clip-no-results-hint">Intenta con otra imagen</div>
                </div>
            `;
            resultsDiv.classList.add('active');
        }

        // Helpers
        function showLoading() {
            container.querySelector('#clip-loading').classList.add('active');
            container.querySelector('#clip-detection').classList.remove('active');
            container.querySelector('#clip-results').classList.remove('active');
            container.querySelector('#clip-error').classList.remove('active');

            // También limpiar elementos dinámicos para evitar duplicación en búsquedas consecutivas
            const detectionDiv = container.querySelector('#clip-detection');
            const itemsDiv = container.querySelector('#clip-detection-items');
            const costDiv = container.querySelector('#clip-detection-cost');
            if (itemsDiv) itemsDiv.innerHTML = '';
            if (costDiv) costDiv.textContent = '';
            if (detectionDiv) {
                const existingIntent = detectionDiv.querySelector('.clip-user-intent');
                if (existingIntent) existingIntent.remove();
            }
        }

        function hideLoading() {
            container.querySelector('#clip-loading').classList.remove('active');
        }

        function showError(msg) {
            const errorDiv = container.querySelector('#clip-error');
            errorDiv.textContent = `❌ ${msg}`;
            errorDiv.classList.add('active');
            container.querySelector('#clip-detection').classList.remove('active');
            container.querySelector('#clip-results').classList.remove('active');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
