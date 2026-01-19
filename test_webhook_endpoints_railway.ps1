# Test script para verificar que los webhooks endpoints funcionan en Railway
# Espera a que Railway complete el deploy y luego testea todos los endpoints

$BASE_URL = "https://clip-comparador-v2.railway.app"
$GOODY_CLIENT_ID = "0fb8cf5d-1ae6-40dd-9741-4004110202a8"

Write-Host "=" * 80 -ForegroundColor Green
Write-Host "🧪 WEBHOOK ENDPOINTS TEST - RAILWAY" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""

# Test 1: Health endpoint
Write-Host "📍 Test 1: GET /api/webhooks/health" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "$BASE_URL/api/webhooks/health" -Method GET -UseBasicParsing
    Write-Host "✅ Success:" $response.StatusCode -ForegroundColor Green
    Write-Host "   Response:" $response.Content -ForegroundColor Green
}
catch {
    Write-Host "❌ Error:" $_.Exception.Message -ForegroundColor Red
    Write-Host "   Status Code:" $_.Exception.Response.StatusCode -ForegroundColor Red
}
Write-Host ""

# Test 2: Test endpoint
Write-Host "📍 Test 2: GET /api/webhooks/test" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "$BASE_URL/api/webhooks/test" -Method GET -UseBasicParsing
    Write-Host "✅ Success:" $response.StatusCode -ForegroundColor Green
    Write-Host "   Response:" $response.Content -ForegroundColor Green
}
catch {
    Write-Host "❌ Error:" $_.Exception.Message -ForegroundColor Red
    Write-Host "   Status Code:" $_.Exception.Response.StatusCode -ForegroundColor Red
}
Write-Host ""

# Test 3: Global test endpoint
Write-Host "📍 Test 3: GET /test-global" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "$BASE_URL/test-global" -Method GET -UseBasicParsing
    Write-Host "✅ Success:" $response.StatusCode -ForegroundColor Green
    Write-Host "   Response:" $response.Content -ForegroundColor Green
}
catch {
    Write-Host "❌ Error:" $_.Exception.Message -ForegroundColor Red
    Write-Host "   Status Code:" $_.Exception.Response.StatusCode -ForegroundColor Red
}
Write-Host ""

# Test 4: Admin panel test endpoints (require authentication)
Write-Host "📍 Test 4: Admin endpoints (would require login)" -ForegroundColor Yellow
Write-Host "   POST /admin/clients/$GOODY_CLIENT_ID/test-connectivity" -ForegroundColor Yellow
Write-Host "   POST /admin/clients/$GOODY_CLIENT_ID/resync-integration" -ForegroundColor Yellow
Write-Host ""

Write-Host "=" * 80 -ForegroundColor Green
Write-Host "✨ Tests completados" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
