# Propuesta: Validar con Evidencia Soporte de SO para Políticas de Seguridad

**Issue:** #245: [HERMES][P1][remediation] Validar con evidencia si una remediación redujo el riesgo
**Fecha:** 2026-09-01 12:40 UTC

## Resumen

El issue pide validar con evidencia si un SO soporta políticas de seguridad específicas (FileVault, SIP, etc.) antes de aplicarlas.

## Enfoque Recomendado

### 1. Diccionario de políticas por SO

Crear un registro de políticas soportadas por SO:

| SO | Política | evidencia necesaria | comandos de verificación |
|----|----------|---------------------|--------------------------|
| macOS | FileVault | `fdesetup status` | `fdesetup status` |
| macOS | SIP | `csrutil status` | `csrutil status` (recovery) |
| Windows | BitLocker | `manage-bde -status` | PowerShell `Get-BitLockerVolume` |
| Linux | LUKS | `cryptsetup luksDump` | `lsblk -f` |

### 2. Validación automatizada

```python
# lucidfence/core/os_validation.py
POLICY_CHECKS = {
    "macos": {
        "filevault": ["fdesetup", "status"],
        "sip": ["csrutil", "status"],
    },
    "windows": {...},
    "linux": {...},
}
```

### 3. Resultado

Devolver un veredicto por política:
- `supported`: el SO soporta la política
- `enabled`: la política está activa
- `unsupported`: el SO no soporta esta política
- `unknown`: no se pudo determinar

## Conclusión

La implementación es straightforward: diccionario de checkers por SO + validación automatizada.

---

*Generado automáticamente por agente-developer el 2026-09-01 12:40 UTC*
