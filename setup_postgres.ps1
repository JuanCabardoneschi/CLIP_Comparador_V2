# Script de ayuda para configurar PostgreSQL local en Windows
# Ejecutar después de instalar PostgreSQL

Write-Host "🚀 CLIP Comparador V2 - Setup PostgreSQL Local" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si PostgreSQL está en el PATH
Write-Host "🔍 Verificando instalación de PostgreSQL..." -ForegroundColor Yellow
try {
    $pgVersion = & psql --version 2>&1
    Write-Host "✅ PostgreSQL encontrado: $pgVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ PostgreSQL no encontrado en el PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Solución:" -ForegroundColor Yellow
    Write-Host "   1. Instala PostgreSQL desde: https://www.postgresql.org/download/windows/" -ForegroundColor White
    Write-Host "   2. O agrega PostgreSQL al PATH:" -ForegroundColor White
    Write-Host '      $env:Path += ";C:\Program Files\PostgreSQL\15\bin"' -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "📋 Pasos para configurar la base de datos local:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  Crear la base de datos (requiere contraseña de postgres):" -ForegroundColor Yellow
Write-Host '   psql -U postgres -c "CREATE DATABASE clip_comparador_v2;"' -ForegroundColor White
Write-Host ""

Write-Host "2️⃣  Copiar y configurar archivo .env.local:" -ForegroundColor Yellow
Write-Host "   cp .env.local.example .env.local" -ForegroundColor White
Write-Host "   Edita .env.local con tu contraseña de PostgreSQL" -ForegroundColor White
Write-Host ""

Write-Host "3️⃣  Inicializar la base de datos:" -ForegroundColor Yellow
Write-Host "   # Cargar variables de entorno" -ForegroundColor White
Write-Host '   Get-Content .env.local | ForEach-Object { if($_ -match "^([^=]+)=(.*)$") { [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }' -ForegroundColor Cyan
Write-Host ""
Write-Host "   # Ejecutar script de inicialización" -ForegroundColor White
Write-Host "   python setup_local_postgres.py" -ForegroundColor Cyan
Write-Host ""

Write-Host "4️⃣  Ejecutar Flask en modo desarrollo:" -ForegroundColor Yellow
Write-Host "   cd clip_admin_backend" -ForegroundColor White
Write-Host "   python app.py" -ForegroundColor Cyan
Write-Host ""

Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Preguntar si quiere ejecutar el paso 1
$response = Read-Host "¿Quieres crear la base de datos ahora? (s/n)"
if ($response -eq "s" -or $response -eq "S") {
    Write-Host ""
    Write-Host "🔄 Creando base de datos..." -ForegroundColor Yellow
    
    try {
        & psql -U postgres -c "CREATE DATABASE clip_comparador_v2;"
        Write-Host "✅ Base de datos 'clip_comparador_v2' creada exitosamente" -ForegroundColor Green
        
        # Preguntar si quiere crear usuario específico
        $createUser = Read-Host "¿Quieres crear un usuario específico para la app? (s/n)"
        if ($createUser -eq "s" -or $createUser -eq "S") {
            $username = Read-Host "Nombre de usuario (default: clip_admin)"
            if ([string]::IsNullOrWhiteSpace($username)) { $username = "clip_admin" }
            
            $password = Read-Host "Contraseña para $username" -AsSecureString
            $passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))
            
            & psql -U postgres -c "CREATE USER $username WITH PASSWORD '$passwordPlain';"
            & psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE clip_comparador_v2 TO $username;"
            
            Write-Host "✅ Usuario '$username' creado y permisos otorgados" -ForegroundColor Green
            Write-Host ""
            Write-Host "📝 Usa esta cadena de conexión en .env.local:" -ForegroundColor Yellow
            Write-Host "DATABASE_URL=postgresql://$username`:$passwordPlain@localhost:5432/clip_comparador_v2" -ForegroundColor Cyan
        }
        
    } catch {
        Write-Host "❌ Error al crear la base de datos" -ForegroundColor Red
        Write-Host "   Verifica que PostgreSQL esté corriendo y que tengas la contraseña correcta" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "📖 Documentación completa en: docs/SETUP_POSTGRES_LOCAL.md" -ForegroundColor Cyan
Write-Host ""
