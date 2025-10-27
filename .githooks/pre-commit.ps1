# Pre-commit hook para PowerShell/Windows
# Valida sintaxis de archivos Python antes de permitir commit

Write-Host "🔍 Validando sintaxis de archivos Python..." -ForegroundColor Cyan

# Obtener archivos .py staged
$pythonFiles = git diff --cached --name-only --diff-filter=ACM | Where-Object { $_ -match '\.py$' }

if (-not $pythonFiles) {
    Write-Host "✅ No hay archivos Python en este commit" -ForegroundColor Green
    exit 0
}

$hasErrors = $false

foreach ($file in $pythonFiles) {
    if (Test-Path $file) {
        Write-Host "   Compilando: $file" -ForegroundColor Gray
        $output = python -m py_compile $file 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ ERROR DE SINTAXIS en: $file" -ForegroundColor Red
            Write-Host $output -ForegroundColor Red
            $hasErrors = $true
        }
    }
}

if ($hasErrors) {
    Write-Host ""
    Write-Host "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌" -ForegroundColor Red
    Write-Host "❌ COMMIT BLOQUEADO: Hay errores de sintaxis en archivos Python" -ForegroundColor Red
    Write-Host "❌ Arregla los errores antes de hacer commit" -ForegroundColor Red
    Write-Host "❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "✅ Todos los archivos Python tienen sintaxis válida" -ForegroundColor Green
exit 0
