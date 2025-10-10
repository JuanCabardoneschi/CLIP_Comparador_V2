# CLIP Comparador V2 - Script de Arranque Corregido
Write-Host "🚀 Iniciando CLIP Comparador V2..." -ForegroundColor Green
Write-Host "🌐 URL del sistema: http://localhost:5000" -ForegroundColor Cyan
Write-Host "👤 Usuario demo: admin@demo.com / admin123" -ForegroundColor Cyan
Write-Host "⚠️  Para detener el servidor presiona Ctrl+C" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Magenta

# Activar entorno virtual y ejecutar Flask
try {
    # Verificar que existe el entorno virtual
    if (Test-Path ".\venv\Scripts\python.exe") {
        Write-Host "✅ Entorno virtual encontrado" -ForegroundColor Green
        
        # Verificar que existe el directorio del backend
        if (Test-Path ".\clip_admin_backend\app.py") {
            Write-Host "✅ Backend encontrado" -ForegroundColor Green
            
            # Ejecutar Flask con la ruta completa del Python del venv
            Write-Host "🔄 Iniciando servidor Flask..." -ForegroundColor Yellow
            Set-Location -Path ".\clip_admin_backend"
            & "..\venv\Scripts\python.exe" "app.py"
        } else {
            Write-Host "❌ Error: No se encuentra clip_admin_backend\app.py" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Error: No se encuentra el entorno virtual en .\venv" -ForegroundColor Red
        Write-Host "💡 Ejecuta: python -m venv venv" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Error ejecutando el script: $_" -ForegroundColor Red
    exit 1
}
