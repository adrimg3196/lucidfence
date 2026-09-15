# Propuesta de Producto: ZK-Geofence - Atestación Criptográfica de Ubicación Preservando la Privacidad

## 1. Resumen Ejecutivo
ZK-Geofence permite a los dispositivos probar que se encuentran dentro de una geocerca autorizada (como un centro de datos, oficina de gobierno o jurisdicción fiscal) utilizando Pruebas de Conocimiento Cero (Zero-Knowledge Proofs). El UEM o auditor recibe una prueba criptográfica verificable sin conocer las coordenadas exactas de latitud y longitud ni el historial de movimiento del usuario.

## 2. Definición del Problema
- Organizaciones con estrictos requisitos de privacidad de empleados (GDPR, regulaciones laborales) enfrentan resistencia para desplegar geofencing por el riesgo de rastreo de ubicación.
- Los auditores externos de cumplimiento necesitan verificar que el acceso a datos corporativos ocurrió desde zonas permitidas sin acceder al rastro de GPS del personal.

## 3. Especificación Funcional
- **Generación de Prueba ZK Local**: El cliente genera una prueba matemática de que la coordenada $(lat, lon)$ pertenece al polígono $P$ definido en `internal/domain/fence`.
- **Verificación Determinista**: El servidor LucidFence o adaptador UEM verifica la firma y validez de la prueba ZK en $\mathcal{O}(1)$ sin descifrar nunca las coordenadas reales.
- **Exportación en Reportes Auditables**: Formato de evidencia compatible con el generador de reportes en `internal/reports`.

## 4. Arquitectura de Implementación (Go / Local-First)
- **Nuevo Paquete Domain**: `internal/domain/zkattest` (circuitos criptográficos deterministas en Go nativo sin dependencias pesadas).
- **Integración con API**: Endpoint `/api/v1/attestations` para verificación local de pruebas.
