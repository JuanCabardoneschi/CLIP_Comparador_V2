$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path logs | Out-Null

$clients = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/clients/list -Method GET
if (-not $clients.success) { throw 'Bad clients response' }
$apiKey = $clients.clients[0].api_key

$img = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAGgwJ/lwVvAAAAAElFTkSuQmCC'

$bodyTrue = @{ image = $img; top_k = 3; max_results = 2; apply_pair_exclusion = $true } | ConvertTo-Json
$respTrue = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/search/gpt4v-unified -Method POST -Headers @{ 'X-API-Key' = $apiKey; 'Content-Type' = 'application/json' } -Body $bodyTrue
$respTrue | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 logs\unified_true.json

$bodyFalse = @{ image = $img; top_k = 3; max_results = 2; apply_pair_exclusion = $false } | ConvertTo-Json
$respFalse = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/search/gpt4v-unified -Method POST -Headers @{ 'X-API-Key' = $apiKey; 'Content-Type' = 'application/json' } -Body $bodyFalse
$respFalse | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 logs\unified_false.json

Write-Host 'DONE'
