# Propuesta de Producto: GhostFence - Protocolo Autónomo de Aislamiento de Emergencia Air-Gap

## 1. Resumen Ejecutivo
GhostFence es un mecanismo autónomo de contención inmediata ante situaciones de riesgo crítico o evasión de geocerca combinada con manipulación de postura. Si un dispositivo compromete su cifrado o falsifica la ubicación mientras pierde comunicación con el servidor UEM, el motor de LucidFence activa de forma local e imperativa el aislamiento de interfaces de red con un mecanismo seguro de contingencia (Break-Glass local cifrado).

## 2. Definición del Problema
- Cuando un dispositivo robado se introduce en un entorno aislado de Faraday o sin red, la orden de Remote Wipe enviada desde la consola UEM central nunca llega.
- Se requiere que el dispositivo tome decisiones de autoconservación y contención de datos localmente cuando el nivel de riesgo supere el umbral máximo (`risk_score == 100`).

## 3. Especificación Funcional
- **Regla de Disparo Autónomo**: Se ejecuta directamente en el runtime local de LucidFence ante la combinación de `integrity_breach` + `boundary_violation` + `loss_of_uem_heartbeat`.
- **Aislamiento Selectivo**: Corta el tráfico de datos corporativos manteniendo únicamente comunicación cifrada por canal seguro local o BLE de emergencia.
- **Protocolo Break-Glass**: El administrador local puede restaurar el estado mediante un PIN de emergencia de un solo uso derivado argon2id generado localmente durante el enrolamiento del tenant.

## 4. Arquitectura de Implementación (Go / Local-First)
- **Nuevo Paquete Domain**: `internal/domain/ghostfence`.
- **Integración con Motor y Guardarraíles**: Respeto estricto del modo `observe` por defecto y comprobación de la autorización previa de acciones imperativas destructivas.
