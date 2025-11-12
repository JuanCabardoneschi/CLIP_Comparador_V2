# Script: run_autocrop_all_clients.ps1
# Ejecuta auto_optimize_crops.py para todos los clientes activos, todas las categorías.
# Genera CSV consolidado por fecha y recalcula centroides al finalizar cada cliente.

param(
    [double]$Threshold = 0.003,
    [switch]$DryRun,
    [switch]$Adaptive,
    [switch]$RequirePositive
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "BATCH AUTOCROP - Todos los clientes" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Threshold: $Threshold" -ForegroundColor Yellow
Write-Host "Dry-run: $DryRun" -ForegroundColor Yellow
Write-Host "Adaptive: $Adaptive" -ForegroundColor Yellow
Write-Host "Require-positive: $RequirePositive" -ForegroundColor Yellow
Write-Host ""

# Activar venv si existe
$venvPath = "C:\Personal\CLIP_Comparador_V2\venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activando venv..." -ForegroundColor Green
    & $venvPath
}

# Cambiar al directorio backend
Set-Location "C:\Personal\CLIP_Comparador_V2\clip_admin_backend"

# Obtener lista de clientes activos
Write-Host "Obteniendo clientes activos..." -ForegroundColor Green
$clientsJson = python -c @"
import sys
sys.path.append('C:/Personal/CLIP_Comparador_V2/clip_admin_backend')
from wsgi import create_app
app = create_app()
from app.models.client import Client
import json
ctx = app.app_context()
ctx.push()
clients = Client.query.filter_by(is_active=True).all()
print(json.dumps([{'id': str(c.id), 'name': c.name} for c in clients]))
ctx.pop()
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al obtener clientes" -ForegroundColor Red
    exit 1
}

$clients = $clientsJson | ConvertFrom-Json
Write-Host "Clientes encontrados: $($clients.Count)" -ForegroundColor Cyan

$totalProcessed = 0
$totalApplied = 0

foreach ($client in $clients) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Magenta
    Write-Host "Cliente: $($client.name)" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    
    # Construir argumentos
    $args = @(
        "C:\Personal\CLIP_Comparador_V2\clip_admin_backend\tools\auto_optimize_crops.py",
        "--threshold", $Threshold,
        "--category-like", "%"
    )
    
    if ($DryRun) { $args += "--dry-run" }
    if ($Adaptive) { $args += "--adaptive" }
    if ($RequirePositive) { $args += "--require-positive" }
    
    # Ejecutar autocrop
    Write-Host "Ejecutando autocrop..." -ForegroundColor Yellow
    & python @args
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error en autocrop para cliente $($client.name)" -ForegroundColor Red
        continue
    }
    
    # Parsear resumen del output (última línea con "Resumen:")
    # Formato esperado: "📊 Resumen: total=X aplicados=Y ..."
    # Por simplicidad, incrementamos contadores manualmente aquí
    
    # Recalcular centroides si no es dry-run
    if (-not $DryRun) {
        Write-Host "Recalculando centroides para cliente $($client.name)..." -ForegroundColor Yellow
        $recalcResult = python -c @"
import sys
sys.path.append('C:/Personal/CLIP_Comparador_V2/clip_admin_backend')
from wsgi import create_app
app = create_app()
from app.blueprints.embeddings import recalculate_category_centroids
ctx = app.app_context()
ctx.push()
result = recalculate_category_centroids(client_id='$($client.id)')
print(result)
ctx.pop()
"@
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Centroides recalculados" -ForegroundColor Green
        } else {
            Write-Host "⚠️ Error recalculando centroides" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "BATCH COMPLETADO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total clientes procesados: $($clients.Count)" -ForegroundColor Green
Write-Host ""
Write-Host "CSVs generados en: clip_admin_backend/logs/autocrop_results_*.csv" -ForegroundColor Yellow
