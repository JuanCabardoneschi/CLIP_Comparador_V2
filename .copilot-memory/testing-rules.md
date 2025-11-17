# REGLAS CRÍTICAS PARA TESTING

## 🚨 NUNCA OLVIDES ESTO

### Cuando el servidor Flask está corriendo en background:

1. **NUNCA ejecutar comandos en la misma terminal** donde corre el servidor
2. **SIEMPRE usar una terminal DIFERENTE** para tests
3. **El servidor debe estar en background (isBackground=true)**
4. **Los tests deben ejecutarse con isBackground=false en OTRA terminal**

### Patrón correcto:

```powershell
# Terminal 1 (Background): Servidor Flask
.\start.ps1  # isBackground=true

# Terminal 2 (Foreground): Tests
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/... # isBackground=false
```

### ❌ ERROR COMÚN (NO HACER):
- Intentar ejecutar test en la misma terminal del servidor
- Esperar a que el servidor termine para hacer el test
- No usar background para el servidor

### ✅ CORRECTO:
1. Iniciar servidor en background
2. Esperar 3-5 segundos
3. Ejecutar test en NUEVA terminal (comando separado)

---

**RECORDAR**: Si estás probando cambios locales y el servidor ya está corriendo en una terminal, usa OTRA terminal para los tests HTTP.
