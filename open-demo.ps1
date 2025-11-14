# Script para abrir las demos desde file:// (sin servidor local)
# Uso: .\open-demo.ps1 [clean|standalone]

param(
    [string]$Version = "standalone"
)

$DemoPath = Join-Path $PSScriptRoot "clip_admin_backend\app\static"

switch ($Version.ToLower()) {
    "clean" {
        $File = "demo-store-clean.html"
        Write-Host "🚀 Abriendo demo-store-clean.html..." -ForegroundColor Cyan
        Write-Host "   Incluye selector de entorno (Local/Railway)" -ForegroundColor Gray
    }
    "standalone" {
        $File = "demo-store-standalone.html"
        Write-Host "🚀 Abriendo demo-store-standalone.html..." -ForegroundColor Cyan
        Write-Host "   Optimizado solo para Railway Production" -ForegroundColor Gray
    }
    default {
        Write-Host "❌ Versión no válida. Usa 'clean' o 'standalone'" -ForegroundColor Red
        exit 1
    }
}

$FullPath = Join-Path $DemoPath $File

if (Test-Path $FullPath) {
    $FileUri = "file:///$($FullPath -replace '\\', '/')"
    Write-Host "📂 Ruta: $FileUri" -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Características:" -ForegroundColor Yellow
    Write-Host "   • Funciona sin servidor local (desde file://)" -ForegroundColor Gray
    Write-Host "   • Apunta a Railway Production por defecto" -ForegroundColor Gray
    Write-Host "   • Widget cargado desde Railway" -ForegroundColor Gray
    Write-Host ""
    Write-Host "⚠️  NOTA: Si ves errores CORS:" -ForegroundColor Yellow
    Write-Host "   Opción 1: Abrir con Chrome sin CORS" -ForegroundColor Gray
    Write-Host "   Start-Process 'chrome.exe' -ArgumentList '--disable-web-security --user-data-dir=C:/temp/chrome-dev $FileUri'" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Opción 2: Acceder directamente desde Railway" -ForegroundColor Gray
    Write-Host "   https://clipcomparadorv2-production.up.railway.app/static/$File" -ForegroundColor DarkGray
    Write-Host ""
    
    Start-Process $FileUri
} else {
    Write-Host "❌ Error: No se encontró $File en $DemoPath" -ForegroundColor Red
    exit 1
}
