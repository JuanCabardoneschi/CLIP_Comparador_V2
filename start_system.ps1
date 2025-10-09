# CLIP Comparador V2 - Script de Arranque Simple
Write-Host "Iniciando CLIP Comparador V2..." -ForegroundColor Green
Write-Host "URL del sistema: http://localhost:5000" -ForegroundColor Cyan
Write-Host "Usuario demo: admin@demo.com / admin123" -ForegroundColor Cyan
Write-Host "Para detener el servidor presiona Ctrl+C" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Magenta

# Comando que funciona correctamente
.\venv\Scripts\Activate.ps1; cd clip_admin_backend; python app.py
