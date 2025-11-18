# 🧪 TEST RÁPIDO: Nueva Búsqueda Textual V2
# Two-Stage Retrieval con auto-generación de sinónimos

$ErrorActionPreference = "Stop"

$BASE_URL = "http://localhost:5000"
$API_KEY = "clip_f47ac10b58cc4372a5670e02b2c3d479"  # Eve's Store

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                                   ║" -ForegroundColor Cyan
Write-Host "║         🆕 TEST: Nueva Búsqueda Textual V2                       ║" -ForegroundColor Cyan
Write-Host "║         Two-Stage Retrieval + Auto-Sinónimos GPT-4               ║" -ForegroundColor Cyan
Write-Host "║                                                                   ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Test-NewTextSearch {
    param(
        [string]$Query,
        [int]$Limit = 5
    )
    
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host "🔍 Query: '$Query'" -ForegroundColor White
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Yellow
    
    $headers = @{
        "X-API-Key" = $API_KEY
        "Content-Type" = "application/json"
    }
    
    $body = @{
        query = $Query
        limit = $Limit
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$BASE_URL/api/search/text" `
            -Method POST `
            -Headers $headers `
            -Body $body `
            -TimeoutSec 10
        
        if ($response.success) {
            Write-Host "✅ Búsqueda exitosa" -ForegroundColor Green
            Write-Host ""
            
            # Información de expansión
            Write-Host "📝 Query original: $($response.query)" -ForegroundColor Cyan
            $expandedCount = $response.expanded_terms.Count
            $expandedPreview = ($response.expanded_terms | Select-Object -First 8) -join ", "
            if ($expandedCount -gt 8) { $expandedPreview += "..." }
            Write-Host "🔄 Términos expandidos ($expandedCount): $expandedPreview" -ForegroundColor Cyan
            Write-Host "📊 Stage 1 candidates: $($response.stage1_candidates)" -ForegroundColor Cyan
            Write-Host "⏱️  Processing time: $($response.processing_time)s" -ForegroundColor Cyan
            Write-Host ""
            
            # Resultados
            $resultsCount = $response.results.Count
            Write-Host "🎯 Resultados ($resultsCount):" -ForegroundColor Green
            
            if ($resultsCount -gt 0) {
                foreach ($i in 0..($resultsCount-1)) {
                    $result = $response.results[$i]
                    $num = $i + 1
                    
                    Write-Host ""
                    Write-Host "  $num. $($result.name)" -ForegroundColor White
                    Write-Host "     Similitud: $($result.similarity) | Precio: `$$($result.price)" -ForegroundColor Gray
                    Write-Host "     Categoría: $($result.category)" -ForegroundColor Gray
                    Write-Host "     SKU: $($result.sku) | Stock: $($result.stock)" -ForegroundColor Gray
                    
                    # Atributos
                    if ($result.attributes) {
                        $attrs = @()
                        $result.attributes.PSObject.Properties | ForEach-Object {
                            if ($_.Value) {
                                $attrs += "$($_.Name): $($_.Value)"
                            }
                        }
                        if ($attrs.Count -gt 0) {
                            Write-Host "     Atributos: $($attrs -join ', ')" -ForegroundColor Gray
                        }
                    }
                }
            } else {
                Write-Host "  ⚠️  No se encontraron resultados" -ForegroundColor Yellow
            }
            
            return $true
        } else {
            Write-Host "❌ Error: $($response.error)" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "❌ Error: $_" -ForegroundColor Red
        return $false
    }
}

# Tests principales
Write-Host "📋 Ejecutando tests..." -ForegroundColor White
Write-Host ""

$queries = @(
    "short rojo",
    "shorts",
    "remera",
    "delantal",
    "gorra"
)

$passed = 0
$failed = 0

foreach ($query in $queries) {
    if (Test-NewTextSearch -Query $query -Limit 5) {
        $passed++
    } else {
        $failed++
    }
    Start-Sleep -Milliseconds 500
}

# Resumen
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    RESUMEN DE TESTS                               ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Exitosos: $passed" -ForegroundColor Green
Write-Host "❌ Fallidos: $failed" -ForegroundColor Red
Write-Host "📊 Total: $($passed + $failed)" -ForegroundColor White
$successRate = if (($passed + $failed) -gt 0) { ($passed / ($passed + $failed) * 100) } else { 0 }
Write-Host ""
Write-Host "🎯 Tasa de éxito: $([math]::Round($successRate, 1))%" -ForegroundColor $(if ($successRate -ge 80) { "Green" } else { "Red" })
Write-Host ""
