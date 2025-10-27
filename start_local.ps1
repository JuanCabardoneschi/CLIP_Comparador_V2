# Script para iniciar CLIP Comparador V2 en desarrollo local
# Uso: .\start_local.ps1

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " CLIP Comparador V2 - Desarrollo Local" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Agregar PostgreSQL al PATH si no esta
$pgPath = "C:\Program Files\PostgreSQL\18\bin"
if ($env:PATH -notlike "*$pgPath*") {
    Write-Host "Agregando PostgreSQL al PATH..." -ForegroundColor Yellow
    $env:PATH += ";$pgPath"
}

# Ir al directorio raiz del proyecto
$rootDir = "C:\Personal\CLIP_Comparador_V2"
Set-Location $rootDir

# Verificar .env.local
if (-not (Test-Path ".env.local")) {
    Write-Host "ERROR: Archivo .env.local no encontrado" -ForegroundColor Red
    Write-Host "Ejecuta: Copy-Item .env.local.example .env.local" -ForegroundColor Yellow
    exit 1
}

Write-Host "Activando entorno virtual..." -ForegroundColor Yellow
& "$rootDir\venv\Scripts\Activate.ps1"

Write-Host ""
Write-Host "URL: http://localhost:5000" -ForegroundColor Green
Write-Host "Admin: admin / admin123" -ForegroundColor White
Write-Host "Demo: demo / demo123" -ForegroundColor White
Write-Host ""
Write-Host "Presiona Ctrl+C para detener" -ForegroundColor Yellow
Write-Host ""

# Iniciar Flask
Set-Location "$rootDir\clip_admin_backend"
python wsgi.py
