#!/usr/bin/env pwsh
# Monitor Railway deployment and logs in real-time

param(
    [string]$ServiceName = "clip-comparador-v2",
    [int]$RefreshSeconds = 5
)

Write-Host "🚀 Railway Deployment Monitor" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host "Monitorando: $ServiceName" -ForegroundColor Cyan
Write-Host "Intervalo: $RefreshSeconds segundos" -ForegroundColor Cyan
Write-Host ""

# Function to check if Railway CLI is installed
function Test-RailwayCLI {
    try {
        $version = & railway version 2>&1
        return $true
    }
    catch {
        return $false
    }
}

# Check Railway CLI
if (-not (Test-RailwayCLI)) {
    Write-Host "❌ Railway CLI no está instalado" -ForegroundColor Red
    Write-Host "Instálalo desde: https://railway.app/docs/cli" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternativa: Ver logs en https://dashboard.railway.app" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Railway CLI detectado" -ForegroundColor Green
Write-Host ""

# Alternative: Use curl to test endpoints
Write-Host "Testing endpoints..." -ForegroundColor Cyan

$endpoints = @(
    @{
        name = "Health Check"
        url = "https://clip-comparador-v2.railway.app/"
        method = "GET"
    },
    @{
        name = "Webhooks Health"
        url = "https://clip-comparador-v2.railway.app/api/webhooks/health"
        method = "GET"
    },
    @{
        name = "Webhooks Test"
        url = "https://clip-comparador-v2.railway.app/api/webhooks/test"
        method = "GET"
    },
    @{
        name = "Global Test"
        url = "https://clip-comparador-v2.railway.app/test-global"
        method = "GET"
    }
)

foreach ($endpoint in $endpoints) {
    Write-Host ""
    Write-Host "🔍 Testing: $($endpoint.name)" -ForegroundColor Cyan
    Write-Host "   URL: $($endpoint.url)" -ForegroundColor Gray
    
    try {
        $response = Invoke-WebRequest -Uri $endpoint.url -Method $endpoint.method -UseBasicParsing -TimeoutSec 10
        Write-Host "   ✅ Status: $($response.StatusCode)" -ForegroundColor Green
        if ($response.Content) {
            $content = $response.Content
            if ($content.Length -gt 100) {
                $content = $content.Substring(0, 100) + "..."
            }
            Write-Host "   📝 Response: $content" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "   ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            Write-Host "   Status Code: $($_.Exception.Response.StatusCode)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "✨ Test completado" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
