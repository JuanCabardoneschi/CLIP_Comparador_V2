# Script interactivo para tareas comunes CLIP
# Ubicación: tools/tareas_clip.ps1

function Ejecutar-Tarea {
    param (
        [string]$Tarea,
        [string]$Modo # "AUTO", "PREMIUM", "GRATIS"
    )

    switch ($Tarea) {
        "iniciar_sistema" {
            Write-Host "Iniciando sistema local..."
            .\start.ps1
        }
        "subir_git" {
            Write-Host "Subiendo cambios a Git..."
            git add .
            git commit -m "Commit automático"
            git push origin main
        }
        "sincronizar_main" {
            Write-Host "Sincronizando con Main..."
            git pull origin main
        }
        "backup_db" {
            Write-Host "Creando backup de la base de datos local..."
            python backup_local_db.py
        }
        "restaurar_db" {
            Write-Host "Restaurando base de datos desde Railway..."
            .\restore_from_railway.ps1
        }
        default {
            if ($Modo -eq "PREMIUM") {
                Write-Host "Esta tarea se ejecutará con modelo PREMIUM (requiere API/modelo externo)."
                # Aquí podrías llamar a un script externo, API, etc.
            } else {
                Write-Host "Tarea no reconocida o no parametrizada."
            }
        }
    }
}

# Menú interactivo
Write-Host "Selecciona la tarea a ejecutar:"
Write-Host "1. Iniciar sistema"
Write-Host "2. Subir cambios a Git"
Write-Host "3. Sincronizar con Main"
Write-Host "4. Backup base de datos"
Write-Host "5. Restaurar base de datos"
Write-Host "6. Otra (modelo PREMIUM)"

$tareaSeleccionada = Read-Host "Ingresa el número de la tarea"
$modo = "AUTO" # Puedes cambiar a "PREMIUM" o "GRATIS" según tu lógica

switch ($tareaSeleccionada) {
    "1" { Ejecutar-Tarea "iniciar_sistema" $modo }
    "2" { Ejecutar-Tarea "subir_git" $modo }
    "3" { Ejecutar-Tarea "sincronizar_main" $modo }
    "4" { Ejecutar-Tarea "backup_db" $modo }
    "5" { Ejecutar-Tarea "restaurar_db" $modo }
    "6" { Ejecutar-Tarea "otra" "PREMIUM" }
    default { Write-Host "Opción no válida." }
}
