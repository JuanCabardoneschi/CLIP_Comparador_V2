param(
    [switch]$SkipTests,
    [switch]$Force
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "    DEPLOY A RAILWAY - CLIP Comparador V2" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar directorio
if (-not (Test-Path ".git")) {
    Write-Host "ERROR: No estás en el directorio raíz del repositorio" -ForegroundColor Red
    exit 1
}

# Verificar cambios
$status = git status --porcelain 2>&1
if ($LASTEXITCODE -ne 0 -or -not $status) {
    Write-Host "No hay cambios para commitear" -ForegroundColor Yellow
    exit 0
}

Write-Host "Cambios detectados:" -ForegroundColor Green
git status --short

# Selector de tipo
Write-Host ""
Write-Host "Selecciona el tipo de cambio:" -ForegroundColor Cyan
Write-Host '1) feat     - Nueva funcionalidad'
Write-Host '2) fix      - Corrección de bug'
Write-Host '3) refactor - Refactorización'
Write-Host '4) perf     - Mejora de performance'
Write-Host '5) style    - Cambios de estilo'
Write-Host '6) docs     - Documentación'
Write-Host '7) test     - Tests'
Write-Host '8) chore    - Mantenimiento'
Write-Host '9) hotfix   - Corrección urgente'
Write-Host ""

do {
    $choice = Read-Host "Opción (1-9)"
    $valid = $choice -match '^[1-9]$'
    if (-not $valid) {
        Write-Host "Opción inválida" -ForegroundColor Red
    }
} until ($valid)

$types = @{ "1"="feat"; "2"="fix"; "3"="refactor"; "4"="perf"; "5"="style"; "6"="docs"; "7"="test"; "8"="chore"; "9"="hotfix" }
$commitType = $types[$choice]

# Mensaje
Write-Host ""
Write-Host "Describe el cambio:" -ForegroundColor Cyan
do {
    $message = Read-Host "Mensaje"
    $valid = $message.Length -ge 10
    if (-not $valid) {
        Write-Host "El mensaje debe tener al menos 10 caracteres" -ForegroundColor Red
    }
} until ($valid)

$commitMessage = "${commitType}: ${message}"

# Tests
if (-not $SkipTests) {
    Write-Host ""
    Write-Host "Ejecutaste tests locales? (s/n):" -ForegroundColor Cyan -NoNewline
    $response = Read-Host
    if ($response -ne 's' -and $response -ne 'S') {
        Write-Host "Considera ejecutar tests antes de deploy" -ForegroundColor Yellow
        $continue = Read-Host "Continuar sin tests? (s/n)"
        if ($continue -ne 's' -and $continue -ne 'S') {
            Write-Host "Deploy cancelado" -ForegroundColor Yellow
            exit 0
        }
    }
}

# Resumen
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "RESUMEN DEL DEPLOY" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tipo:    $commitType"
Write-Host "Mensaje: $commitMessage"
Write-Host ""
git diff --name-status
Write-Host ""

# Confirmación
Write-Host "Estás seguro de hacer deploy a Railway? (s/n):" -ForegroundColor Yellow -NoNewline
$confirm = Read-Host
if ($confirm -ne 's' -and $confirm -ne 'S') {
    Write-Host "Deploy cancelado" -ForegroundColor Yellow
    exit 0
}

# Deploy
Write-Host ""
Write-Host "Ejecutando deploy..." -ForegroundColor Cyan
Write-Host ""

git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al agregar archivos" -ForegroundColor Red
    exit 1
}

git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al crear commit" -ForegroundColor Red
    exit 1
}

Write-Host ""
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al hacer push" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "            DEPLOY EXITOSO" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Railway está procesando el deploy automáticamente" -ForegroundColor Cyan
Write-Host "Monitorea: https://railway.app/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Si necesitas rollback:" -ForegroundColor Yellow
Write-Host "  git revert HEAD"
Write-Host "  git push origin main"
Write-Host ""
