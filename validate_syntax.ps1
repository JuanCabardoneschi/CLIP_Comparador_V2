# Script de validación de sintaxis Python
# Ejecuta ANTES de hacer commit para evitar errores en Railway

Write-Host "`n🔍 VALIDACIÓN DE SINTAXIS - CLIP Comparador V2" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

$pythonFiles = Get-ChildItem -Path "clip_admin_backend" -Filter "*.py" -Recurse | Where-Object { 
    $_.FullName -notmatch '__pycache__' -and $_.FullName -notmatch 'venv'
}

Write-Host "`n📋 Archivos a validar: $($pythonFiles.Count)" -ForegroundColor Yellow

$hasErrors = $false
$errorFiles = @()

foreach ($file in $pythonFiles) {
    $relativePath = $file.FullName.Replace((Get-Location).Path + "\", "")
    Write-Host "   Compilando: $relativePath" -ForegroundColor Gray
    
    $output = python -m py_compile $file.FullName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ❌ ERROR" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        $hasErrors = $true
        $errorFiles += $relativePath
    } else {
        Write-Host "   ✅ OK" -ForegroundColor Green
    }
}

Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan

if ($hasErrors) {
    Write-Host "❌ VALIDACIÓN FALLIDA" -ForegroundColor Red
    Write-Host "`nArchivos con errores:" -ForegroundColor Red
    foreach ($file in $errorFiles) {
        Write-Host "   - $file" -ForegroundColor Red
    }
    Write-Host "`n⚠️  NO HAGAS COMMIT HASTA ARREGLAR ESTOS ERRORES ⚠️" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "✅ TODOS LOS ARCHIVOS SON VÁLIDOS" -ForegroundColor Green
    Write-Host "   Puedes hacer commit con seguridad" -ForegroundColor Green
    exit 0
}
