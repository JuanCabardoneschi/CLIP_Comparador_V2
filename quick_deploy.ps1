#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy rápido a Railway (sin validaciones extensivas)
.DESCRIPTION
    Versión simplificada para cambios pequeños o urgentes
.EXAMPLE
    .\quick_deploy.ps1 -Message "fix: corregir búsqueda de colores"
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$Message,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("feat", "fix", "refactor", "perf", "style", "docs", "test", "chore", "hotfix")]
    [string]$Type = "fix"
)

$ErrorActionPreference = "Stop"

Write-Host "`n🚀 Quick Deploy a Railway`n" -ForegroundColor Cyan

# Si no hay mensaje, pedirlo
if (-not $Message) {
    Write-Host "Describe el cambio:" -ForegroundColor Yellow
    $Message = Read-Host
    if (-not $Message) {
        Write-Host "❌ Debes proporcionar un mensaje" -ForegroundColor Red
        exit 1
    }
}

$fullMessage = "${Type}: ${Message}"

# Mostrar lo que se va a hacer
Write-Host "`nCommit: $fullMessage" -ForegroundColor Green
git status --short

# Confirmar
Write-Host "`n¿Continuar? (s/n): " -ForegroundColor Yellow -NoNewline
$confirm = Read-Host
if ($confirm -ne 's' -and $confirm -ne 'S') {
    Write-Host "❌ Cancelado" -ForegroundColor Red
    exit 0
}

# Deploy
Write-Host "`n📦 Ejecutando deploy...`n" -ForegroundColor Cyan
git add .
git commit -m $fullMessage
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Deploy exitoso - Railway está procesando..." -ForegroundColor Green
    Write-Host "🔗 https://railway.app/`n" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Error en deploy" -ForegroundColor Red
    exit 1
}
