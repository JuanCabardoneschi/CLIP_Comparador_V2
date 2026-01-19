# Monitor Railway logs for webhook processing
# Usage: .\monitor_webhook_logs.ps1

Write-Host "🔍 Monitoring Railway logs for webhook events..." -ForegroundColor Cyan
Write-Host "The deployment may take 30-60 seconds. Wait for the green checkmark before updating." -ForegroundColor Yellow
Write-Host ""

# Give a few seconds for the command to start
Start-Sleep -Seconds 2

# Monitor logs continuously - look for webhook patterns
railway logs --follow | Select-String -Pattern '(WEBHOOK|📦|📁|🔍|✅|❌|⚠️|CATEGORÍA)' -Context 0,0

Write-Host ""
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Gray
