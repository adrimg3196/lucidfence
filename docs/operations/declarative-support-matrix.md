# Matriz de Soporte Declarativa Unificada (DDM + DSC + AMAPI)

Este documento centraliza y consolida la matriz de soporte para la capa de configuración/enforcement declarativa en LucidFence.

## Límite Transversal: Sin Geolocalización Local

**Ninguno de los mecanismos declarativos (Apple DDM, Windows DSC o Android AMAPI) dispone de primitivas de geolocalización local o evaluación de posición.**

El trigger de geocerca reside de forma exclusiva en el engine y en los adapters de LucidFence. El servidor calcula el estado de geocerca (`inside` / `outside`) y decide qué conjunto/documento de políticas declarativas activar en cada transición de estado en el dispositivo. Las tecnologías declarativas actúan únicamente como la capa de enforcement y convergencia local del estado deseado una vez que LucidFence lo determina.

---

## Matriz de Soporte Unificada

| Plataforma | Mecanismo declarativo | Versión mínima | Modo de gestión requerido | Flag de capacidad en el adapter | Qué NO cubre |
| :--- | :--- | :--- | :--- | :--- | :--- |
| iOS | Apple DDM | 15.0 | Supervisado o User Enrollment | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| iPadOS | Apple DDM | 15.0 | Supervisado o User Enrollment | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| macOS | Apple DDM | 13.0 | MDM Enrolled | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| tvOS | Apple DDM | 16.0 | Supervisado | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| visionOS | Apple DDM | 1.1 | MDM Enrolled | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| watchOS | Apple DDM | 10.0 | MDM Enrolled | `supports_ddm` (Jamf) | Geolocalización nativa, creación/subida de declarations personalizadas en Jamf Pro (fase offline) |
| Windows | PowerShell DSC v3 | 10.0 | PowerShell 7.2+ (Fallback DSC v2 en PS 5.1) | `supports_dsc` (WindowsConformidad) | Geolocalización nativa, instalación del motor DSC o PowerShell 7 si no está preinstalado |
| Android | Android AMAPI (Pendiente de PR #53) | Pendiente | Pendiente de PR #53 (COBO / Work Profile) | `supports_amapi_policy` (Pendiente) | Geolocalización nativa, creación automática de la enterprise de Google sin credenciales |
