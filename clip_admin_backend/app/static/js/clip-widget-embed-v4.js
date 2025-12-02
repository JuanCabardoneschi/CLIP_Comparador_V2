/**
 * CLIP Widget V4 - Overlay Only Mode
 * Modo overlay únicamente - Búsqueda visual inteligente con GPT-4V
 *
 * Uso:
 * <script>
 *   window.CLIPWidget = { apiKey: "YOUR_KEY", serverUrl: "https://..." };
 * </script>
 * <script src="/static/js/clip-widget-embed-v4.js"></script>
 *
 * API Global:
 * window.CLIPV2.overlay.open()  - Abrir modal
 * window.CLIPV2.overlay.close() - Cerrar modal
 */

(function() {
    'use strict';

    if (!window.CLIPWidget || !window.CLIPWidget.apiKey) {
        console.error('CLIP Widget: Se requiere window.CLIPWidget = { apiKey: "YOUR_KEY" }');
        return;
    }

    // Crear namespace global
    window.CLIPV2 = window.CLIPV2 || {};

    let overlayContainer = null;
    let widgetContainer = null;
    let selectedFile = null;
    let isSearching = false; // Flag para prevenir búsquedas simultáneas

    const config = {
        apiKey: window.CLIPWidget.apiKey,
        serverUrl: window.CLIPWidget.serverUrl || 'https://clipcomparadorv2-production.up.railway.app'
    };

    // ==================== CSS STYLES ====================
    const overlayStyle = document.createElement('style');
    overlayStyle.textContent = `
        /* Overlay Container */
        .clip-overlay-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            z-index: 99998;
            display: none;
            animation: clipFadeIn 0.3s ease;
        }
        .clip-overlay-backdrop.active {
            display: block;
        }
        .clip-overlay-container {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            max-width: 1000px;
            max-height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            z-index: 99999;
            display: none;
            overflow: hidden;
            animation: clipSlideUp 0.3s ease;
        }
        .clip-overlay-container.active {
            display: flex;
            flex-direction: column;
        }
        .clip-overlay-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .clip-overlay-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0;
            line-height: 1.3;
        }
        .clip-overlay-subtitle {
            font-size: 0.9rem;
            opacity: 0.9;
            margin: 0.25rem 0 0 0;
            font-weight: 400;
        }
        .clip-overlay-close {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }
        .clip-overlay-close:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .clip-overlay-content {
            flex: 1;
            overflow-y: auto;
            padding: 0;
        }

        /* Widget Content */
        .clip-widget-wrap {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: white;
            overflow: hidden;
            max-width: 100%;
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
            font-size: 1.4rem;
        }

        /* Tab Content */
        .clip-tab-content {
            display: none;
            padding: 2rem;
        }
        .clip-tab-content.active {
            display: block;
        }
        .clip-search-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #1e293b;
            margin: 0 0 0.5rem 0;
            text-align: center;
        }
        .clip-search-subtitle {
            font-size: 1rem;
            color: #64748b;
            margin: 0 0 2rem 0;
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
            margin-bottom: 1.5rem;
        }
        .clip-upload-area:hover {
            border-color: #667eea;
            background: #f1f5f9;
        }
        .clip-upload-area.dragover {
            border-color: #667eea;
            background: #eef2ff;
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
            margin-bottom: 1.5rem;
        }
        .clip-preview.active {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            justify-content: center;
        }
        .clip-preview-container {
            position: relative;
            display: inline-block;
            flex-shrink: 0;
        }
        .clip-preview-img {
            max-width: 300px;
            max-height: 300px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .clip-remove-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(239, 68, 68, 0.9);
            color: white;
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            cursor: pointer;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }
        .clip-remove-btn:hover {
            background: rgba(220, 38, 38, 1);
        }

        /* Search Button */
        .clip-search-btn {
            width: 100%;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        .clip-search-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        .clip-search-btn:active {
            transform: translateY(0);
        }
        .clip-search-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none !important;
            background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
            box-shadow: none;
        }
        .clip-search-btn:disabled:hover {
            transform: none !important;
            box-shadow: none;
        }

        /* Text Search */
        .clip-text-input {
            width: 100%;
            padding: 1rem 1.5rem;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            font-size: 1rem;
            margin-bottom: 1rem;
            transition: border-color 0.2s;
        }
        .clip-text-input:focus {
            outline: none;
            border-color: #667eea;
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
        .clip-loading.compact {
            padding: 1rem;
            text-align: center;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .clip-loading.compact .clip-loading-spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f1f5f9;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem auto;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .clip-loading.compact .clip-loading-text {
            font-size: 1rem;
        }
        .clip-loading.compact .clip-loading-steps {
            font-size: 0.85rem;
        }
        .clip-loading-spinner {
            width: 60px;
            height: 60px;
            border: 4px solid #f1f5f9;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1.5rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .clip-loading-text {
            font-size: 1.2rem;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .clip-loading-steps {
            font-size: 0.95rem;
            color: #64748b;
            line-height: 1.8;
        }

        /* Detection */
        .clip-detection {
            display: none;
            padding: 1.5rem 2rem;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
            border-radius: 12px;
            margin: 0 2rem 1.5rem 2rem;
        }
        .clip-detection.active {
            display: block;
        }
        .clip-detection-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1e40af;
            margin-bottom: 1rem;
        }
        .clip-detection-items {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        .clip-detection-tag {
            background: white;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-weight: 600;
            color: #1e40af;
            border: 2px solid #93c5fd;
            font-size: 0.95rem;
        }
        .clip-user-intent {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            color: #1e40af;
            font-size: 0.95rem;
            margin-top: 1rem;
            border-left: 4px solid #3b82f6;
        }
        .clip-detection-cost {
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 0.75rem;
        }

        /* Results */
        .clip-results {
            display: none;
            padding: 0 2rem 2rem 2rem;
        }
        .clip-results.active {
            display: block;
        }
        .clip-category-section {
            margin-bottom: 2rem;
        }
        .clip-category-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            margin-bottom: 1rem;
            color: white;
        }
        .clip-category-name {
            font-size: 1.2rem;
            font-weight: 700;
        }
        .clip-category-count {
            font-size: 0.95rem;
            opacity: 0.9;
        }
        .clip-product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1.5rem;
        }
        .clip-product {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
        }
        .clip-product:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }
        .clip-product-img-wrap {
            position: relative;
            width: 100%;
            height: 200px;
            overflow: hidden;
            background: #f8fafc;
        }
        .clip-product-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .clip-similarity-badge,
        .clip-badge-percentage {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(102, 126, 234, 0.95);
            color: white;
            padding: 0.3rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .clip-product-info {
            padding: 1rem;
            display: flex;
            flex-direction: column;
            flex: 1;
        }
        .clip-product-name {
            font-size: 0.95rem;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }
        .clip-product-price {
            font-size: 1.1rem;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 0.5rem;
        }
        .clip-product-stock {
            font-size: 0.85rem;
            font-weight: 600;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            margin-top: 0.5rem;
        }
        .clip-product-stock.in-stock {
            background: #dcfce7;
            color: #166534;
        }
        .clip-product-stock.out-stock {
            background: #fee2e2;
            color: #991b1b;
        }

        /* Info Banner (Text Search) */
        .clip-info-banner {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid #3b82f6;
        }
        .clip-info-banner-item {
            margin-bottom: 0.75rem;
        }
        .clip-info-banner-item:last-child {
            margin-bottom: 0;
        }
        .clip-info-banner-label {
            font-weight: 700;
            color: #1e40af;
            margin-right: 0.5rem;
        }
        .clip-info-banner-content {
            display: inline-flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.25rem;
        }
        .clip-banner-badge {
            background: white;
            color: #1e40af;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid #93c5fd;
        }
        .clip-banner-badge-highlight {
            background: #667eea;
            color: white;
            border-color: #667eea;
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

        /* Error */
        .clip-error {
            display: none;
            padding: 1rem 1.5rem;
            background: #fee2e2;
            color: #991b1b;
            border-radius: 12px;
            margin: 0 2rem 1.5rem 2rem;
            font-weight: 600;
        }
        .clip-error.active {
            display: block;
        }

        /* Animations */
        @keyframes clipFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes clipSlideUp {
            from { opacity: 0; transform: translate(-50%, -45%); }
            to { opacity: 1; transform: translate(-50%, -50%); }
        }
    `;
    document.head.appendChild(overlayStyle);

    // ==================== HTML STRUCTURE ====================
    function buildOverlay() {
        const backdrop = document.createElement('div');
        backdrop.className = 'clip-overlay-backdrop';
        backdrop.onclick = closeOverlay;

        const container = document.createElement('div');
        container.className = 'clip-overlay-container';
        container.onclick = (e) => e.stopPropagation();

        container.innerHTML = `
            <div class="clip-overlay-header">
                <div>
                    <h2 class="clip-overlay-title">🤖 Búsqueda Inteligente</h2>
                    <p class="clip-overlay-subtitle">Encuentra productos similares con IA</p>
                </div>
                <button class="clip-overlay-close" onclick="window.CLIPV2.overlay.close()">×</button>
            </div>
            <div class="clip-overlay-content">
                <div id="clip-widget-overlay"></div>
            </div>
        `;

        document.body.appendChild(backdrop);
        document.body.appendChild(container);

        return { backdrop, container };
    }

    function buildWidget() {
        widgetContainer = document.getElementById('clip-widget-overlay');
        if (!widgetContainer) {
            console.error('CLIP Widget: Container #clip-widget-overlay not found');
            return;
        }

        widgetContainer.innerHTML = `
            <div class="clip-widget-wrap">
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
                        <div class="clip-loading compact" id="clip-loading-compact">
                            <div class="clip-loading-spinner"></div>
                            <div class="clip-loading-text" id="clip-loading-text-compact">Analizando imagen con IA...</div>
                            <div class="clip-loading-steps" id="clip-loading-steps-compact">
                                <div>✓ Detectando categorías con GPT-4V</div>
                                <div>✓ Analizando similitud visual con CLIP</div>
                                <div>✓ Buscando productos coincidentes</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tab Content: Text Search -->
                <div class="clip-tab-content" id="clip-text-tab">
                    <h2 class="clip-search-title">Describe lo que buscas</h2>
                    <p class="clip-search-subtitle">Escribe qué producto necesitas y lo encontraremos</p>

                    <input
                        type="text"
                        class="clip-text-input"
                        id="clip-text-input"
                        placeholder="Ej: remera negra con bolsillo"
                    >

                    <button class="clip-search-btn" id="clip-text-search-btn">
                        🔍 Buscar Productos
                    </button>
                </div>

                <!-- Loading State -->
                <div class="clip-loading" id="clip-loading">
                    <div class="clip-loading-spinner"></div>
                    <div class="clip-loading-text" id="clip-loading-text">Analizando imagen con IA...</div>
                    <div class="clip-loading-steps" id="clip-loading-steps">
                        <div>✓ Detectando categorías con GPT-4V</div>
                        <div>✓ Analizando similitud visual con CLIP</div>
                        <div>✓ Buscando productos coincidentes</div>
                    </div>
                </div>

                <!-- Detection Results -->
                <div class="clip-detection" id="clip-detection">
                    <div class="clip-detection-title">🎯 Categorías detectadas:</div>
                    <div class="clip-detection-items" id="clip-detection-items"></div>
                    <div class="clip-detection-cost" id="clip-detection-cost"></div>
                </div>

                <!-- Error -->
                <div class="clip-error" id="clip-error"></div>

                <!-- Results -->
                <div class="clip-results" id="clip-results"></div>
            </div>
        `;

        attachEventListeners();
    }

    // ==================== EVENT LISTENERS ====================
    function attachEventListeners() {
        const upload = widgetContainer.querySelector('#clip-upload');
        const fileInput = widgetContainer.querySelector('#clip-file-input');
        const preview = widgetContainer.querySelector('#clip-preview');
        const previewImg = widgetContainer.querySelector('#clip-preview-img');
        const removeBtn = widgetContainer.querySelector('#clip-remove-btn');
        const textSearchBtn = widgetContainer.querySelector('#clip-text-search-btn');
        const textInput = widgetContainer.querySelector('#clip-text-input');

        // Tabs
        widgetContainer.querySelectorAll('.clip-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;

                widgetContainer.querySelectorAll('.clip-tab').forEach(t => t.classList.remove('active'));
                widgetContainer.querySelectorAll('.clip-tab-content').forEach(c => c.classList.remove('active'));

                tab.classList.add('active');
                widgetContainer.querySelector(`#clip-${tabName}-tab`).classList.add('active');

                clearResults();
            });
        });

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

                // Resetear spinner antes de buscar
                resetLoadingSpinner();

                // Buscar automáticamente al subir imagen
                performGPT4VSearch(selectedFile);
            };
            reader.readAsDataURL(file);
        }

        removeBtn.addEventListener('click', () => {
            selectedFile = null;
            preview.classList.remove('active');
            upload.style.display = 'block';
            fileInput.value = '';
            clearResults();
            // Asegurar que el loading compacto también se oculta
            const loadingCompact = widgetContainer.querySelector('#clip-loading-compact');
            if (loadingCompact) loadingCompact.classList.remove('active');

            // Resetear spinner compacto al estado original (por si estaba en check verde)
            resetLoadingSpinner();
        });

        // Text search button
        textSearchBtn.addEventListener('click', () => {
            const query = textInput.value.trim();
            if (!query || isSearching) return;
            performTextSearch(query);
        });

        // Text input Enter key
        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = textInput.value.trim();
                if (query && !isSearching) performTextSearch(query);
            }
        });
    }

    // ==================== API CALLS ====================
    function performGPT4VSearch(file) {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('max_results_per_category', '8');
        formData.append('similarity_threshold', '0.65');

        showLoading();

        const currentApiKey = window.CLIPWidget?.apiKey || config.apiKey;

        fetch(`${config.serverUrl}/api/search/gpt4v-unified`, {
            method: 'POST',
            headers: { 'X-API-Key': currentApiKey },
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                hideLoading();
                showError(data.message || 'Error en la búsqueda');
                return;
            }

            // 🚨 VERIFICACIÓN CRÍTICA: Si GPT-4V no detectó categorías válidas
            const categoriesDetected = data.detection?.categories_detected || data.detection?.categories_detected_raw || [];
            const userIntent = data.detection?.user_intent || data.detection?.mensaje_usuario || '';

            if (categoriesDetected.length === 0) {
                // Detener spinner y mostrar búsqueda completada
                hideLoading();
                showLoadingSuccess();

                // Mostrar bloque de detección con intención (si existe)
                if (userIntent) {
                    const detectionDiv = widgetContainer.querySelector('#clip-detection');
                    const itemsDiv = widgetContainer.querySelector('#clip-detection-items');
                    const costDiv = widgetContainer.querySelector('#clip-detection-cost');

                    // Limpiar contenedores
                    itemsDiv.innerHTML = '';
                    costDiv.textContent = '';
                    const existingIntent = detectionDiv.querySelector('.clip-user-intent');
                    if (existingIntent) existingIntent.remove();

                    // Mostrar user_intent EXACTAMENTE como en displayDetection (sin tags de categorías)
                    const intentHtml = `
                        <div class="clip-user-intent">
                            ${userIntent}
                        </div>
                    `;
                    costDiv.insertAdjacentHTML('beforebegin', intentHtml);
                    detectionDiv.classList.add('active');

                    // Hacer scroll al bloque de detección
                    setTimeout(() => {
                        detectionDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 100);

                    // NO mostrar showError() para permitir que el mensaje de intención sea visible
                } else {
                    // Solo si no hay intención, mostrar error genérico
                    showError('No se detectaron categorías válidas para esta imagen. Por favor, sube una imagen relacionada con los productos disponibles en la tienda.');
                }
                return;
            }

            // Mostrar detección
            hideLoading();
            displayDetection(data.detection);

            // Mostrar resultados
            if (data.metadata.total_products_found > 0) {
                displayResults(data.results_by_category, data.metadata);
            } else {
                hideLoading();
                showNoResults();
            }
        })
        .catch(err => {
            hideLoading();
            showError('Error de conexión. Intenta nuevamente.');
            console.error(err);
        });
    }

    function performTextSearch(query) {
        // Marcar búsqueda en progreso
        isSearching = true;

        // Deshabilitar botón y cambiar texto
        const textSearchBtn = widgetContainer.querySelector('#clip-text-search-btn');
        if (textSearchBtn) {
            textSearchBtn.disabled = true;
            textSearchBtn.innerHTML = '<div style="width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; display: inline-block; vertical-align: middle; margin-right: 8px; animation: spin 1s linear infinite;"></div> Buscando...';
        }

        showLoading();

        // Buscar elementos tanto en loading full como compact
        const loadingText = widgetContainer.querySelector('#clip-loading-text');
        const loadingSteps = widgetContainer.querySelector('#clip-loading-steps');
        const loadingTextCompact = widgetContainer.querySelector('#clip-loading-text-compact');
        const loadingStepsCompact = widgetContainer.querySelector('#clip-loading-steps-compact');

        if (loadingText) loadingText.textContent = 'Buscando productos...';
        if (loadingSteps) loadingSteps.style.display = 'none';
        if (loadingTextCompact) loadingTextCompact.textContent = 'Buscando productos...';
        if (loadingStepsCompact) loadingStepsCompact.style.display = 'none';

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
                if (data.categories_available || data.categories_searched) {
                    showNoResults({
                        message: data.message || 'No se detectó ninguna categoría válida',
                        categories_available: data.categories_available || [],
                        categories_searched: data.categories_searched || []
                    });
                } else {
                    showError(data.message || data.error || 'Error en la búsqueda');
                }
                return;
            }

            widgetContainer.querySelector('#clip-detection').classList.remove('active');

            if (data.filtering?.top_5_productos && data.filtering.top_5_productos.length > 0) {
                displayTextSearchResults(data);
            } else {
                showNoResults(data.user_feedback || data.partial_match_info || { message: 'No se encontraron productos' });
            }
        })
        .catch(err => {
            hideLoading();
            showError('Error de conexión. Intenta nuevamente.');
            console.error(err);
        })
        .finally(() => {
            // Marcar búsqueda completada
            isSearching = false;

            // Restaurar botón
            const textSearchBtn = widgetContainer.querySelector('#clip-text-search-btn');
            if (textSearchBtn) {
                textSearchBtn.disabled = false;
                textSearchBtn.innerHTML = '🔍 Buscar Productos';
            }

            // Restaurar textos originales en ambos loadings
            const loadingText = widgetContainer.querySelector('#clip-loading-text');
            const loadingSteps = widgetContainer.querySelector('#clip-loading-steps');
            const loadingTextCompact = widgetContainer.querySelector('#clip-loading-text-compact');
            const loadingStepsCompact = widgetContainer.querySelector('#clip-loading-steps-compact');

            if (loadingText) loadingText.textContent = 'Analizando imagen con IA...';
            if (loadingSteps) loadingSteps.style.display = 'block';
            if (loadingTextCompact) loadingTextCompact.textContent = 'Analizando imagen con IA...';
            if (loadingStepsCompact) loadingStepsCompact.style.display = 'block';
        });
    }

    // ==================== DISPLAY FUNCTIONS ====================
    function displayDetection(detection) {
        // NO ocultar preview - permitir cargar otra imagen
        // Cambiar spinner por check de éxito
        showLoadingSuccess();

        const detectionDiv = widgetContainer.querySelector('#clip-detection');
        const itemsDiv = widgetContainer.querySelector('#clip-detection-items');
        const costDiv = widgetContainer.querySelector('#clip-detection-cost');

        itemsDiv.innerHTML = '';
        costDiv.textContent = '';
        const existingIntent = detectionDiv.querySelector('.clip-user-intent');
        if (existingIntent) existingIntent.remove();

        const categories = detection.categories_detected_raw || detection.categories_detected || [];
        const userIntent = detection.user_intent || detection.mensaje_usuario || '';

        itemsDiv.innerHTML = categories.map(cat =>
            `<div class="clip-detection-tag">${cat}</div>`
        ).join('');

        if (userIntent) {
            const intentHtml = `
                <div class="clip-user-intent">
                    ${userIntent}
                </div>
            `;
            costDiv.insertAdjacentHTML('beforebegin', intentHtml);
        }

        detectionDiv.classList.add('active');

        // Hacer scroll al inicio de los resultados
        setTimeout(() => {
            detectionDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    function displayResults(resultsByCategory, metadata) {
        // Ocultar loading compacto si está activo
        const loadingCompact = widgetContainer.querySelector('#clip-loading-compact');
        if (loadingCompact) loadingCompact.classList.remove('active');

        const resultsDiv = widgetContainer.querySelector('#clip-results');

        // Ordenar categorías: primero las que tienen productos, luego las vacías
        const sortedCategories = Object.entries(resultsByCategory).sort(([, dataA], [, dataB]) => {
            const hasProductsA = dataA.products.length > 0 ? 1 : 0;
            const hasProductsB = dataB.products.length > 0 ? 1 : 0;
            return hasProductsB - hasProductsA; // Descendente: con productos primero
        });

        const html = sortedCategories.map(([categoryName, categoryData]) => {
            // Si no hay productos pero hay mensaje de "no similar", mostrar categoría con mensaje
            if (categoryData.products.length === 0) {
                if (categoryData.no_similar_message) {
                    return `
                        <div class="clip-category-section">
                            <div class="clip-category-header">
                                <div class="clip-category-name">${categoryName}</div>
                                <div class="clip-category-count">
                                    0 de ${categoryData.total_in_category} productos
                                </div>
                            </div>
                            <div class="clip-no-results" style="padding: 20px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 8px; margin-top: 12px;">
                                <div style="font-size: 2rem; margin-bottom: 8px;">🔍</div>
                                <div style="font-weight: 500; margin-bottom: 4px;">No se encontraron coincidencias</div>
                                <div style="font-size: 0.875rem;">${categoryData.no_similar_message}</div>
                            </div>
                        </div>
                    `;
                }
                return '';
            }

            // Mapas auxiliares para etiquetas y tipos
            const labelMap = (metadata && metadata.exposed_attribute_labels) || {};
            const typesMap = (metadata && metadata.exposed_attribute_types) || {};

            return `
                <div class="clip-category-section">
                    <div class="clip-category-header">
                        <div class="clip-category-name">${categoryName}</div>
                        <div class="clip-category-count">
                            ${categoryData.results_returned} de ${categoryData.total_in_category} productos
                        </div>
                    </div>
                    <div class="clip-product-grid">
                        ${categoryData.products.map(p => {
                            // Render badges de atributos visibles (provenientes del API ya filtrados)
                            const entries = (p.attributes && typeof p.attributes === 'object')
                                ? Object.entries(p.attributes)
                                : [];

                            const attrBadges = entries
                                .filter(([k]) => k && !['url_producto','product_url'].includes(String(k).toLowerCase()))
                                .map(([k, v]) => {
                                    const kLower = String(k).toLowerCase();
                                    let val = '';
                                    if (v === null || v === undefined) {
                                        val = '';
                                    } else if (Array.isArray(v)) {
                                        // Soportar listas con strings u objetos {label|value|name}
                                        const parts = v.map(item => {
                                            if (item === null || item === undefined) return '';
                                            if (typeof item === 'object') {
                                                return item.label || item.value || item.name || '';
                                            }
                                            return String(item);
                                        }).filter(Boolean);
                                        val = parts.join(', ');
                                    } else if (typeof v === 'object') {
                                        // Objeto único
                                        if ((typesMap[kLower] || '').toLowerCase() === 'url') {
                                            const urlVal = v.url || v.value || '';
                                            if (urlVal) {
                                                const safeUrl = String(urlVal);
                                                const label = labelMap[kLower] || String(k);
                                                return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" style="background:#eef2ff;color:#1e40af;padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:600;border:1px solid #c7d2fe;white-space:nowrap;text-decoration:none;">${label}</a>`;
                                            }
                                        }
                                        val = v.label || v.value || v.name || '';
                                    } else {
                                        val = String(v);
                                    }
                                    const label = labelMap[kLower] || String(k);
                                    const text = val ? `${label}: ${val}` : label;
                                    return `<span style="background:#f1f5f9;color:#0f172a;padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:600;border:1px solid #e2e8f0;white-space:nowrap;">${text}</span>`;
                                })
                                .join(' ');

                            // Link a producto si existe (atributo tipo URL o campo product_url)
                            let productLinkHtml = '';
                            let productUrl = '';
                            if (p.product_url) {
                                if (typeof p.product_url === 'object') {
                                    productUrl = p.product_url.url || p.product_url.value || '';
                                } else {
                                    productUrl = String(p.product_url);
                                }
                                if (productUrl) {
                                    const btn = `<a href="${productUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-block;margin-top:8px;background:#0ea5e9;color:#fff;padding:6px 10px;border-radius:8px;font-size:12px;font-weight:600;text-decoration:none;">Ver producto ↗</a>`;
                                    productLinkHtml = btn;
                                }
                            }

                            // Hacer la imagen clickeable si hay URL
                            const imgContent = productUrl
                                ? `<a href="${productUrl}" target="_blank" rel="noopener noreferrer" style="display:block;height:100%;cursor:pointer;">
                                    <img src="${p.image_url}" alt="${p.name}" class="clip-product-img">
                                   </a>`
                                : `<img src="${p.image_url}" alt="${p.name}" class="clip-product-img">`;

                            return `
                            <div class="clip-product">
                                <div class="clip-product-img-wrap">
                                    ${imgContent}
                                    <div class="clip-similarity-badge">
                                        ${Math.round(p.similarity_score * 100)}% Match
                                    </div>
                                </div>
                                <div class="clip-product-info">
                                    <div class="clip-product-name">${p.name}</div>
                                    <div class="clip-product-price">
                                        ${p.price ? `$${p.price.toFixed(2)}` : 'Consultar'}
                                    </div>
                                    ${attrBadges ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;">${attrBadges}</div>` : ''}
                                    ${productLinkHtml}
                                    ${p.stock !== undefined ? `
                                        <div class="clip-product-stock ${p.stock > 0 ? 'in-stock' : 'out-stock'}" style="margin-top:auto;">
                                            ${p.stock > 0 ? `✓ Stock: ${p.stock}` : '✗ Sin stock'}
                                        </div>
                                    ` : ''}
                                </div>
                            </div>`;
                        }).join('')}
                    </div>
                </div>
            `;
        }).join('');

        resultsDiv.innerHTML = html;
        resultsDiv.classList.add('active');
    }

    function displayTextSearchResults(data) {
        // Mostrar TODOS los atributos visibles, no solo los que coinciden
        // Ajustar cálculo de porcentaje para listas multi-valor
        const resultsDiv = widgetContainer.querySelector('#clip-results');
        const productos = data.filtering.top_5_productos || [];
        const exposedKeys = data.exposed_attribute_keys || [];
        const labelMap = data.exposed_attribute_labels || {};

        const requiredStrong = {};
        const encontrados = (data.analysis && data.analysis.atributos_encontrados) ? data.analysis.atributos_encontrados : [];
        encontrados.forEach(a => {
            const key = (a.atributo_key || '').trim();
            const matchTipo = a.match_tipo || a.matchTipo || a.match_tipo;
            const valorDetectado = a.valor_detectado;
            if (!key) return;
            if (matchTipo === 'value' && valorDetectado !== undefined && valorDetectado !== null) {
                const vNorm = String(valorDetectado).trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'');
                requiredStrong[key] = { values: new Set([vNorm]) };
            } else if (key === 'con_bolsillo') {
                requiredStrong[key] = { values: new Set(['si']) };
            } else {
                requiredStrong[key] = { values: null };
            }
        });

        const requiredStrongKeys = Object.keys(requiredStrong);

        const bannerHtml = renderTestingBanner(data);

        const productosPorCategoria = {};
        productos.forEach(prod => {
            const catName = prod.category || 'Sin categoría';
            if (!productosPorCategoria[catName]) {
                productosPorCategoria[catName] = [];
            }
            productosPorCategoria[catName].push(prod);
        });

        const renderProduct = (prod) => {
            const coverageAttrs = Array.isArray(prod.attributes_coverage) ? prod.attributes_coverage : [];
            const weakMods = Array.isArray(prod.weak_modifiers) ? prod.weak_modifiers : [];

            let strongMatches = 0;
            let strongCriteria = requiredStrongKeys.length;

            const coverageByKey = {};
            coverageAttrs.forEach(a => { coverageByKey[a.key] = a; });

            requiredStrongKeys.forEach(key => {
                const req = requiredStrong[key];
                const item = coverageByKey[key];
                if (!item) return;
                const raw = item.value;
                const valuesList = Array.isArray(raw) ? raw : (raw !== undefined && raw !== null ? [raw] : []);
                let anyMatch = false;
                if (req.values === null) {
                    if (valuesList.length > 0 && valuesList.some(v => String(v).trim())) {
                        anyMatch = true;
                    }
                } else {
                    for (const val of valuesList) {
                        const normVal = String(val).trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'');
                        if (req.values.has(normVal)) {
                            anyMatch = true;
                            break;
                        }
                    }
                }
                if (anyMatch) strongMatches += 1;
            });

            const weakSimilarityMatched = (weakMods.length > 0 && prod.clip_similarity > 0.50);
            const weakMatches = weakSimilarityMatched ? weakMods.length : 0;
            const weakCriteria = weakMods.length;

            const totalCriteria = strongCriteria + weakCriteria;
            const matchedCriteria = strongMatches + weakMatches;
            const matchPercentage = totalCriteria > 0 ? Math.round((matchedCriteria / totalCriteria) * 100) : 0;

            const imgHtml = prod.image_url
                ? `<img src="${prod.image_url}" alt="${prod.name || 'Producto'}" class="clip-product-img">`
                : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:0.8rem;">Sin imagen</div>`;

            const strongBadges = requiredStrongKeys.map(key => {
                const coverage = coverageByKey[key];
                const label = (coverage && (coverage.label || coverage.key)) || key;
                const req = requiredStrong[key];
                const raw = coverage ? coverage.value : undefined;
                const valuesList = Array.isArray(raw) ? raw : (raw !== undefined && raw !== null ? [raw] : []);
                const displayVal = valuesList.map(v => typeof v === 'object' ? (v.label || v.value || v.name || '') : String(v)).filter(Boolean).join(', ');
                let ok = false;
                if (coverage) {
                    if (req.values === null) {
                        ok = valuesList.length > 0;
                    } else {
                        for (const val of valuesList) {
                            const normVal = String(val).trim().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'');
                            if (req.values.has(normVal)) { ok = true; break; }
                        }
                    }
                }
                const icon = ok ? '✅' : '❌';
                const valueSuffix = displayVal ? `: ${displayVal}` : '';
                return `<span style="background:${ok ? '#ecfdf5' : '#fef2f2'};color:${ok ? '#065f46' : '#991b1b'};padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:600;border:1px solid ${ok ? '#a7f3d0' : '#fecaca'};white-space:nowrap;">${icon} ${label}${valueSuffix}</span>`;
            }).join(' ');

            // Mostrar también los atributos visibles NO requeridos para la búsqueda
            const visibleExtraBadges = exposedKeys
                .filter(k => !requiredStrongKeys.includes(k))
                .map(k => {
                    const attrVal = (prod.attributes || {})[k];
                    const label = labelMap[k] || k;
                    if (attrVal === undefined || attrVal === null) return '';
                    let valuesList = Array.isArray(attrVal) ? attrVal : (typeof attrVal === 'object' && attrVal !== null && !Array.isArray(attrVal) ? [attrVal] : [attrVal]);
                    valuesList = valuesList.filter(v => v !== null && v !== undefined);
                    const displayVal = valuesList.map(v => typeof v === 'object' ? (v.label || v.value || v.name || '') : String(v)).filter(Boolean).join(', ');
                    if (!displayVal) return '';
                    return `<span style="background:#f1f5f9;color:#334155;padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:600;border:1px solid #e2e8f0;white-space:nowrap;">${label}: ${displayVal}</span>`;
                })
                .filter(Boolean)
                .join(' ');

            const weakBadges = weakMods.length > 0 ? weakMods.map(mod => {
                const ok = prod.clip_similarity > 0.50;
                const icon = ok ? '✅' : '❌';
                return `<span style="background:${ok ? '#eff6ff' : '#fef2f2'};color:${ok ? '#1e40af' : '#991b1b'};padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:600;border:1px solid ${ok ? '#bfdbfe' : '#fecaca'};white-space:nowrap;">${icon} ${mod}</span>`;
            }).join(' ') : '';

            // Tags coincidentes (si el backend los envía en top_5_productos)
            const tagBadges = Array.isArray(prod.tags_matched) && prod.tags_matched.length > 0
                ? prod.tags_matched.map(t => `<span style="background:#f5f3ff;color:#6d28d9;padding:4px 8px;border-radius:9999px;font-size:11px;font-weight:700;border:1px solid #ddd6fe;white-space:nowrap;">#${t}</span>`).join(' ')
                : '';

            const allBadges = [strongBadges, weakBadges, visibleExtraBadges, tagBadges].filter(x => x).join(' ');

            return `
                <div class="clip-product">
                    <div class="clip-product-img-wrap">
                        ${imgHtml}
                        <span class="clip-badge-percentage">${matchPercentage}%</span>
                    </div>
                    <div class="clip-product-info">
                        <div class="clip-product-name">${prod.name || 'Producto'}</div>
                        <div class="clip-product-price">
                            ${(prod.price !== null && prod.price !== undefined && typeof prod.price === 'number') ? `$${prod.price.toFixed(2)}` : 'Consultar'}
                        </div>
                        ${allBadges ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;">${allBadges}</div>` : ''}
                        ${prod.stock !== undefined ? `
                            <div class="clip-product-stock ${prod.stock > 0 ? 'in-stock' : 'out-stock'}" style="margin-top:auto;">
                                ${prod.stock > 0 ? `✓ Stock: ${prod.stock}` : '✗ Sin stock'}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        };

        const categorySectionsHtml = Object.entries(productosPorCategoria).map(([categoryName, prods]) => {
            return `
                <div class="clip-category-section">
                    <div class="clip-category-header">
                        <div class="clip-category-name">${categoryName}</div>
                        <div class="clip-category-count">${prods.length} producto${prods.length !== 1 ? 's' : ''}</div>
                    </div>
                    <div class="clip-product-grid">
                        ${prods.map(renderProduct).join('')}
                    </div>
                </div>
            `;
        }).join('');

        resultsDiv.innerHTML = `${bannerHtml}${categorySectionsHtml}`;
        resultsDiv.classList.add('active');
    }

    function renderTestingBanner(data) {
        let items = [];

        const categorias = data.detection?.categorias_matched || [];
        if (categorias.length > 0) {
            const cats = categorias.map(cat =>
                `<span class="clip-banner-badge clip-banner-badge-highlight">${cat.name}</span>`
            ).join(' ');
            items.push(`<div class="clip-info-banner-item"><span class="clip-info-banner-label">Buscando en:</span><div class="clip-info-banner-content">${cats}</div></div>`);
        }

        const attrsFuertes = data.analysis?.atributos_encontrados || [];
        if (attrsFuertes.length > 0) {
            const attrs = attrsFuertes.map(a => {
                const label = a.atributo_label || a.atributo_key;
                const value = a.valor_detectado ? `: ${a.valor_detectado}` : '';
                return `<span class="clip-banner-badge">${label}${value}</span>`;
            }).join(' ');
            items.push(`<div class="clip-info-banner-item"><span class="clip-info-banner-label">Filtrando:</span><div class="clip-info-banner-content">${attrs}</div></div>`);
        }

        const attrsDebiles = data.analysis?.modificadores_no_configurados || [];
        if (attrsDebiles.length > 0) {
            const mods = attrsDebiles.map(m =>
                `<span class="clip-banner-badge">${m}</span>`
            ).join(' ');
            items.push(`<div class="clip-info-banner-item"><span class="clip-info-banner-label">Similitud visual:</span><div class="clip-info-banner-content">${mods}</div></div>`);
        }

        if (items.length === 0) return '';

        return `<div class="clip-info-banner">${items.join('')}</div>`;
    }

    function showNoResults(partialMatchInfo) {
        const resultsDiv = widgetContainer.querySelector('#clip-results');

        const categoriesList = partialMatchInfo?.categories_available || partialMatchInfo?.categories_searched;
        const categoriesText = categoriesList && categoriesList.length > 0
            ? `<div style="font-size: 14px; margin-top: 12px; line-height: 1.6;">
                Comercializamos productos de las siguientes categorías: <strong>${categoriesList.join(', ')}</strong>
               </div>`
            : '';

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
                ${categoriesText}
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
                <div class="clip-no-results-hint">Intenta con otra imagen o descripción</div>
            </div>
        `;
        resultsDiv.classList.add('active');
    }

    // ==================== UTILITY FUNCTIONS ====================
    function showLoading() {
        const preview = widgetContainer.querySelector('#clip-preview');
        const loadingCompact = widgetContainer.querySelector('#clip-loading-compact');
        const loadingFull = widgetContainer.querySelector('#clip-loading');

        if (!loadingFull || !loadingCompact) {
            console.error('Loading elements not found');
            return;
        }

        // Si hay preview activo (imagen subida), usar loading compacto al lado
        if (preview && preview.classList.contains('active')) {
            loadingCompact.classList.add('active');
            loadingFull.classList.remove('active');
        } else {
            // Si no hay preview, usar loading full screen
            loadingFull.classList.add('active');
            loadingCompact.classList.remove('active');
        }

        const detection = widgetContainer.querySelector('#clip-detection');
        const results = widgetContainer.querySelector('#clip-results');
        const error = widgetContainer.querySelector('#clip-error');

        if (detection) detection.classList.remove('active');
        if (results) results.classList.remove('active');
        if (error) error.classList.remove('active');

        const detectionDiv = widgetContainer.querySelector('#clip-detection');
        const itemsDiv = widgetContainer.querySelector('#clip-detection-items');
        const costDiv = widgetContainer.querySelector('#clip-detection-cost');
        if (itemsDiv) itemsDiv.innerHTML = '';
        if (costDiv) costDiv.textContent = '';
        if (detectionDiv) {
            const existingIntent = detectionDiv.querySelector('.clip-user-intent');
            if (existingIntent) existingIntent.remove();
        }
    }

    function hideLoading() {
        const loadingFull = widgetContainer.querySelector('#clip-loading');
        const loadingCompact = widgetContainer.querySelector('#clip-loading-compact');
        if (loadingFull) loadingFull.classList.remove('active');
        if (loadingCompact) loadingCompact.classList.remove('active');
    }

    function resetLoadingSpinner() {
        // Resetear spinner compacto al estado original
        const spinner = widgetContainer.querySelector('#clip-loading-compact .clip-loading-spinner');
        if (spinner) {
            spinner.style.border = '4px solid #f1f5f9';
            spinner.style.borderTopColor = '#667eea';
            spinner.style.background = 'none';
            spinner.style.animation = 'spin 1s linear infinite';
            spinner.innerHTML = '';
        }
        const loadingText = widgetContainer.querySelector('#clip-loading-text-compact');
        if (loadingText) loadingText.textContent = 'Analizando imagen con IA...';
        const loadingSteps = widgetContainer.querySelector('#clip-loading-steps-compact');
        if (loadingSteps) loadingSteps.style.display = 'block';
    }

    function showLoadingSuccess() {
        // Reemplazar spinner por check verde de éxito
        const spinner = widgetContainer.querySelector('#clip-loading-compact .clip-loading-spinner');
        if (spinner) {
            spinner.style.border = 'none';
            spinner.style.background = '#10b981';
            spinner.style.animation = 'none';
            spinner.innerHTML = '<div style="color:white;font-size:24px;line-height:40px;">✓</div>';
        }
        const loadingText = widgetContainer.querySelector('#clip-loading-text-compact');
        if (loadingText) loadingText.textContent = '¡Búsqueda completada!';
        const loadingSteps = widgetContainer.querySelector('#clip-loading-steps-compact');
        if (loadingSteps) loadingSteps.style.display = 'none';
    }

    function clearResults() {
        widgetContainer.querySelector('#clip-detection').classList.remove('active');
        widgetContainer.querySelector('#clip-results').classList.remove('active');
        widgetContainer.querySelector('#clip-error').classList.remove('active');
        widgetContainer.querySelector('#clip-loading').classList.remove('active');
        widgetContainer.querySelector('#clip-loading-compact').classList.remove('active');
    }

    function showError(msg) {
        const errorDiv = widgetContainer.querySelector('#clip-error');
        errorDiv.textContent = `❌ ${msg}`;
        errorDiv.classList.add('active');
        widgetContainer.querySelector('#clip-detection').classList.remove('active');
        widgetContainer.querySelector('#clip-results').classList.remove('active');
    }

    // ==================== OVERLAY CONTROLS ====================
    function openOverlay() {
        if (!overlayContainer) {
            overlayContainer = buildOverlay();
            buildWidget();
        }

        overlayContainer.backdrop.classList.add('active');
        overlayContainer.container.classList.add('active');

        const content = overlayContainer.container.querySelector('.clip-overlay-content');
        if (content) content.scrollTop = 0;

        document.body.style.overflow = 'hidden';
    }

    function closeOverlay() {
        if (!overlayContainer) return;

        overlayContainer.backdrop.classList.remove('active');
        overlayContainer.container.classList.remove('active');

        document.body.style.overflow = '';
    }

    // ==================== PUBLIC API ====================
    window.CLIPV2.overlay = {
        open: openOverlay,
        close: closeOverlay
    };

    console.log('✅ CLIP Widget V4 - Modo Overlay Único activado');
})();
