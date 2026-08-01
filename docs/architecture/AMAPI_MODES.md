# Android Management API (AMAPI) — Matriz de Modos de Gestión (COBO vs BYOD/COPE)

Fecha: 2026-07-28
Estado: VIGENTE
Contexto: Georreferenciación declarativa y cumplimiento de políticas de geocercas en dispositivos Android.

## 1. Introducción
El API de Gestión de Android (AMAPI) permite definir políticas de forma declarativa. El servidor publica un documento de política deseado (desired-state JSON) y el dispositivo converge de manera autónoma hacia ese estado.

Sin embargo, las capacidades de AMAPI están acotadas según el **modo de gestión** (Management Mode) del dispositivo. Esta matriz detalla qué restricciones de geocerca aplicadas mediante LucidFence son válidas para dispositivos totalmente administrados corporativos (COBO) frente a perfiles de trabajo (BYOD/COPE).

---

## 2. Matriz de Soporte de Restricciones por Geocercas

| Restricción AMAPI | Clave AMAPI Policy | Totalmente Administrado (COBO) | Perfil de Trabajo (BYOD / COPE) | Descripción / Comportamiento |
| :--- | :--- | :---: | :---: | :--- |
| **Desactivar Cámara** | `cameraDisabled` | **Sí** (Dispositivo) | **Sí** (Perfil de trabajo) | Desactiva el uso de cámaras de fotos y vídeo. En BYOD solo afecta a las apps del perfil de trabajo. |
| **Control de Apps** | `applications[]` | **Sí** (Dispositivo) | **Sí** (Perfil de trabajo) | Permite forzar instalación (`FORCE_INSTALLED`) o bloquear (`BLOCKED`) aplicaciones específicas en el entorno correspondiente. |
| **Lanzador Kiosk** | `kioskCustomLauncherEnabled` | **Sí** | **No** | Bloquea el dispositivo en modo quiosco de una o múltiples apps. No disponible en perfiles personales / BYOD. |
| **Modo de Ubicación** | `locationMode` | **Sí** | **No** (Controlado por el usuario) | Fuerza el nivel de precisión del GPS (`HIGH_ACCURACY`, `SENSORS_ONLY`, etc.). En BYOD el usuario conserva control total de su privacidad. |
| **Bloqueo de Wi-Fi** | `wifiConfigsLockdownEnabled` | **Sí** | **No** | Evita que el usuario modifique configuraciones de red Wi-Fi administradas. |
| **Reglas de Escalado** | `policyEnforcementRules` | **Sí** | **Limitado** (Solo borrado de Perfil) | Permite configurar reglas automatizadas de bloqueo y borrado si no se cumple la política. |

---

## 3. Comportamientos Detallados y Escalado Declarativo

### Fully Managed (COBO - Corporate-Owned, Business-Only)
- **Control Absoluto:** El servidor LucidFence puede deshabilitar la cámara de forma global, restringir acceso a aplicaciones, forzar el GPS en alta precisión para garantizar el geofencing, y bloquear el dispositivo en modo quiosco.
- **Graduated Enforcement (Escalado Gradual):** Utilizando `policyEnforcementRules`, se pueden establecer flujos de cumplimiento nativos:
  1. **Advertencia (Warn):** Notificación de incumplimiento.
  2. **Bloqueo (Block):** Bloquear el acceso a recursos o aplicaciones corporativas mediante `blockAction` tras un retardo (ej. `blockAfterDays: 1`).
  3. **Wipe Global:** Borrar todo el dispositivo mediante `wipeAction` tras un periodo prolongado (ej. `wipeAfterDays: 5`).

### Work Profile (BYOD - Bring Your Own Device / COPE)
- **Garantía de Privacidad:** Las restricciones están contenidas estrictamente dentro del contenedor corporativo (Work Profile).
- **Control de Cámara Limitado:** La cámara corporativa se desactiva, pero la cámara personal sigue estando disponible para el usuario.
- **Sin Modo Quiosco:** El dispositivo no puede ser bloqueado en un lanzador único corporativo, ya que convive con el lanzador personal.
- **Wipe Acotado:** El escalado mediante `wipeAction` dentro del perfil de trabajo elimina exclusivamente el contenedor corporativo (Work Profile Wipe), dejando intactos los datos personales del usuario.

---

## 4. Estructura de Parche AMAPI (Ejemplo)

A continuación se muestra un ejemplo de política declarativa generada por LucidFence al detectar que un dispositivo Android ha salido de su geocerca permitida:

```json
{
  "cameraDisabled": true,
  "applications": [
    {
      "packageName": "com.android.chrome",
      "installType": "BLOCKED"
    },
    {
      "packageName": "com.lucidfence.agent",
      "installType": "FORCE_INSTALLED"
    }
  ],
  "locationMode": "HIGH_ACCURACY",
  "policyEnforcementRules": [
    {
      "settingName": "cameraDisabled",
      "blockAction": {
        "blockAfterDays": 1
      },
      "wipeAction": {
        "wipeAfterDays": 5
      }
    }
  ]
}
```
