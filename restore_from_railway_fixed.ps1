# Script para restaurar la base de datos desde Railway a PostgreSQL local
# Fecha: 7 de Noviembre, 2025

Write-Host "Restaurando base de datos desde Railway..." -ForegroundColor Cyan
Write-Host ""

# Configuracion
$LOCAL_DB = "clip_comparador_v2"
$LOCAL_USER = "postgres"
$LOCAL_PASSWORD = "Laurana@01"

# 1. Crear base de datos local si no existe
Write-Host "Paso 1: Creando base de datos local..." -ForegroundColor Yellow
$env:PGPASSWORD = $LOCAL_PASSWORD
$checkDB = psql -U $LOCAL_USER -lqt | Select-String -Pattern $LOCAL_DB
if ($checkDB) {
    Write-Host "Base de datos '$LOCAL_DB' ya existe. Deseas eliminarla y recrearla? (S/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Write-Host "Eliminando base de datos existente..." -ForegroundColor Red
        psql -U $LOCAL_USER -c "DROP DATABASE IF EXISTS $LOCAL_DB;"
        psql -U $LOCAL_USER -c "CREATE DATABASE $LOCAL_DB;"
        Write-Host "Base de datos recreada" -ForegroundColor Green
    } else {
        Write-Host "Operacion cancelada" -ForegroundColor Red
        exit
    }
} else {
    psql -U $LOCAL_USER -c "CREATE DATABASE $LOCAL_DB;"
    Write-Host "Base de datos '$LOCAL_DB' creada" -ForegroundColor Green
}

Write-Host ""

# 2. Descargar desde Railway usando railway_db_tool.py
Write-Host "Paso 2: Descargando datos desde Railway..." -ForegroundColor Yellow
python railway_db_tool.py dump-prod
if ($LASTEXITCODE -eq 0) {
    Write-Host "Datos descargados correctamente" -ForegroundColor Green
} else {
    Write-Host "Error descargando datos desde Railway" -ForegroundColor Red
    exit
}

Write-Host ""

# 3. Restaurar en BD local
Write-Host "Paso 3: Restaurando estructura y datos..." -ForegroundColor Yellow

# Restaurar estructura
if (Test-Path "backups\railway_schema.sql") {
    psql -U $LOCAL_USER -d $LOCAL_DB -f backups\railway_schema.sql
    Write-Host "Estructura restaurada" -ForegroundColor Green
}

# Restaurar datos
if (Test-Path "backups\railway_data.sql") {
    psql -U $LOCAL_USER -d $LOCAL_DB -f backups\railway_data.sql
    Write-Host "Datos restaurados" -ForegroundColor Green
}

Write-Host ""

# 4. Verificar datos
Write-Host "Paso 4: Verificando datos restaurados..." -ForegroundColor Yellow
psql -U $LOCAL_USER -d $LOCAL_DB -c "SELECT COUNT(*) as clients FROM clients"
psql -U $LOCAL_USER -d $LOCAL_DB -c "SELECT COUNT(*) as products FROM products"
psql -U $LOCAL_USER -d $LOCAL_DB -c "SELECT COUNT(*) as images FROM images"

Write-Host ""
Write-Host "Restauracion completada!" -ForegroundColor Green
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Cyan
Write-Host "   1. Verifica que .env.local tenga las credenciales correctas" -ForegroundColor White
Write-Host "   2. Ejecuta: .\start_local.ps1" -ForegroundColor White
Write-Host ""
