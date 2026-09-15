# Propuesta de Producto: LucidMesh - Consenso P2P Local de Ubicación y Postura

## 1. Resumen Ejecutivo
LucidMesh introduce una capa de malla peer-to-peer (P2P) efímera y cifrada localmente entre dispositivos administrados de la misma organización que comparten proximidad física (vía Bluetooth LE o Wi-Fi Direct). Diseñada para operar de forma totalmente offline y local-first, LucidMesh permite la validación cruzada de coordenadas y postura sin depender del GPS público ni de antenas de red cuando se detecta jamming, spoofing o entornos sin cobertura.

## 2. Definición del Problema
- Los atacantes pueden falsificar la ubicación GPS (GPS spoofing) o bloquear la señal (GPS jamming) en recintos de alta seguridad.
- Los UEMs tradicionales y motores geofence dependen de señales individuales de dispositivo, vulnerables a manipulaciones locales.
- No existe validación distribuida local sin enviar datos de geolocalización a servidores centralizados en la nube.

## 3. Especificación Funcional
- **Descubrimiento Cifrado Cero-Conocimiento**: Uso de beacons BLE cifrados con claves rotativas de organización derivadas del token local.
- **Consenso de Proximidad Cruzada**: Si 3 o más dispositivos colindantes corroboran presencia en la misma geocerca mientras 1 reporta una ubicación anómala alejada, la puntuación de riesgo de falsificación se eleva automáticamente (`gps_spoofing_risk`).
- **Resiliencia Air-Gapped**: Transferencia de alertas de postura entre nodos sin conexión a internet hasta que un dispositivo de la malla recupere egress con LucidFence server.

## 4. Arquitectura de Implementación (Go / Local-First)
- **Nuevo Paquete Domain**: `internal/domain/mesh` (tipos de consenso, firmas ed25519 locales, distancias de malla).
- **Transporte Local**: Interfaces abstraídas para adaptadores BLE/mDNS locales sin dependencias de terceros no autorizadas.
- **Sin Persistencia Centralizada**: El estado de la malla vive únicamente en memoria volátil durante el ciclo de evaluación (`TryLock`).
