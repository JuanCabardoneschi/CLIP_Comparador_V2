# Script para restaurar la base de datos desde Railway a PostgreSQL local
# Fecha: 17 de Octubre, 2025

Write-Host "🚀 Restaurando base de datos desde Railway..." -ForegroundColor Cyan
Write-Host ""

# Configuración
$LOCAL_DB = "clip_comparador_v2"
$LOCAL_USER = "postgres"
$LOCAL_PASSWORD = "Laurana@01"

# 1. Crear base de datos local si no existe
Write-Host "📦 Paso 1: Creando base de datos local..." -ForegroundColor Yellow
$env:PGPASSWORD = $LOCAL_PASSWORD
$checkDB = psql -U $LOCAL_USER -lqt | Select-String -Pattern $LOCAL_DB
if ($checkDB) {
    Write-Host "⚠️  Base de datos '$LOCAL_DB' ya existe. ¿Deseas eliminarla y recrearla? (S/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Write-Host "🗑️  Eliminando base de datos existente..." -ForegroundColor Red
        psql -U $LOCAL_USER -c "DROP DATABASE IF EXISTS $LOCAL_DB;"
        psql -U $LOCAL_USER -c "CREATE DATABASE $LOCAL_DB;"
        Write-Host "✅ Base de datos recreada" -ForegroundColor Green
    } else {
        Write-Host "❌ Operación cancelada" -ForegroundColor Red
        exit
    }
} else {
    psql -U $LOCAL_USER -c "CREATE DATABASE $LOCAL_DB;"
    Write-Host "✅ Base de datos '$LOCAL_DB' creada" -ForegroundColor Green
}

Write-Host ""

# 2. Restaurar estructura
Write-Host "📋 Paso 2: Restaurando estructura de tablas..." -ForegroundColor Yellow
psql -U $LOCAL_USER -d $LOCAL_DB -f railway_schema.sql
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Estructura restaurada correctamente" -ForegroundColor Green
} else {
    Write-Host "❌ Error restaurando estructura" -ForegroundColor Red
    exit
}

Write-Host ""

# 3. Restaurar datos
Write-Host "📊 Paso 3: Restaurando datos..." -ForegroundColor Yellow
psql -U $LOCAL_USER -d $LOCAL_DB -f railway_data.sql
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Datos restaurados correctamente" -ForegroundColor Green
} else {
    Write-Host "⚠️  Algunos datos pueden no haberse restaurado completamente" -ForegroundColor Yellow
}

Write-Host ""

# 4. Verificar datos
Write-Host "🔍 Paso 4: Verificando datos restaurados..." -ForegroundColor Yellow
psql -U $LOCAL_USER -d $LOCAL_DB -c "SELECT 'clients' as tabla, COUNT(*) as registros FROM clients UNION ALL SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'categories', COUNT(*) FROM categories UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'images', COUNT(*) FROM images UNION ALL SELECT 'api_keys', COUNT(*) FROM api_keys;" | Write-Host -ForegroundColor Cyan

Write-Host ""

# 5. Crear .env.local si no existe
Write-Host "⚙️  Paso 5: Configurando archivo .env.local..." -ForegroundColor Yellow
if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.local.example" ".env.local"
    Write-Host "✅ Archivo .env.local creado desde template" -ForegroundColor Green
    Write-Host "⚠️  IMPORTANTE: Edita .env.local y agrega las credenciales de Cloudinary" -ForegroundColor Yellow
} else {
    Write-Host "ℹ️  Archivo .env.local ya existe" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "🎉 ¡Restauración completada!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Próximos pasos:" -ForegroundColor Cyan
Write-Host "   1. Edita .env.local con las credenciales de Cloudinary de producción" -ForegroundColor White
Write-Host "   2. Ejecuta: cd clip_admin_backend" -ForegroundColor White
Write-Host "   3. Ejecuta: python app.py" -ForegroundColor White
Write-Host ""
Write-Host "🔐 Credenciales de acceso:" -ForegroundColor Cyan
Write-Host "   Super Admin: admin / admin123" -ForegroundColor White
Write-Host "   Cliente Demo: demo / demo123" -ForegroundColor White
Write-Host ""
