# Activa el entorno y ejecuta el script de corrección
# Uso:
#   .\run_fix_external_urls.ps1 -DatabaseUrl "postgresql://usuario:pass@host:5432/db" -DryRun
#   .\run_fix_external_urls.ps1 -DatabaseUrl "postgresql://usuario:pass@host:5432/db"

param(
    [Parameter(Mandatory=$false)] [string]$DatabaseUrl,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Activar venv si existe
$venvActivate = "C:/Personal/CLIP_Comparador_V2/venv/Scripts/Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
}

# Construir comando
$cmd = "python fix_tiendanube_external_urls.py"
if ($DatabaseUrl) {
    $cmd += " --database-url `"$DatabaseUrl`""
}
if ($DryRun) {
    $cmd += " --dry-run"
}

Write-Host "Ejecutando: $cmd"
Invoke-Expression $cmd
