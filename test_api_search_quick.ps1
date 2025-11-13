# Test rápido para /api/search después de reiniciar servidor
$ErrorActionPreference = 'Continue'

Write-Host "`n=== Test /api/search ===" -ForegroundColor Cyan

# 1. Obtener API key de algún cliente
try {
    $clientsResp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/clients/list" -Method GET -TimeoutSec 5
    if ($clientsResp.success -and $clientsResp.clients.Count -gt 0) {
        $apiKey = $clientsResp.clients[0].api_key
        $clientName = $clientsResp.clients[0].name
        Write-Host "✓ Cliente: $clientName" -ForegroundColor Green
        Write-Host "✓ API Key obtenida: $($apiKey.Substring(0,8))..." -ForegroundColor Green
    } else {
        Write-Host "✗ No se pudieron obtener clientes" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Error obteniendo clientes: $_" -ForegroundColor Red
    exit 1
}

# 2. Imagen de prueba en base64 (1x1 pixel transparente PNG)
$testImageBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

# 3. POST a /api/search
try {
    Write-Host "`n→ POST /api/search..." -ForegroundColor Yellow
    
    $formData = @{
        image = "data:image/png;base64,$testImageBase64"
        limit = "3"
    }
    
    $headers = @{
        "X-API-Key" = $apiKey
    }
    
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/search" `
                                   -Method POST `
                                   -Headers $headers `
                                   -Body ($formData | ConvertTo-Json) `
                                   -ContentType "application/json" `
                                   -TimeoutSec 30
    
    if ($response.success) {
        Write-Host "✓ /api/search FUNCIONA" -ForegroundColor Green
        Write-Host "  - Categorías detectadas: $($response.categories_detected.Count)" -ForegroundColor Cyan
        Write-Host "  - Productos retornados: $($response.products.Count)" -ForegroundColor Cyan
        
        # Guardar respuesta completa para inspección
        $response | ConvertTo-Json -Depth 8 | Out-File -Encoding UTF8 "logs\test_api_search_response.json"
        Write-Host "  - Respuesta guardada en logs\test_api_search_response.json" -ForegroundColor Gray
    } else {
        Write-Host "✗ /api/search respondió con success=false" -ForegroundColor Red
        Write-Host "  Error: $($response.error)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "✗ Error llamando /api/search: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Test completado ===" -ForegroundColor Cyan
