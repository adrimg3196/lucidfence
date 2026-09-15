# Propuesta de Producto: ChronosFence - Motor Probabilístico de Riesgo Espacio-Temporal

## 1. Resumen Ejecutivo
ChronosFence añade una dimensión temporal y predictiva al motor de riesgo de LucidFence 2.0 (`internal/domain/risk`). Mediante la compilación de perfiles locales de velocidad probabilística y patrones de permanencia sin almacenar coordenadas crudas, ChronosFence anticipa violaciones de geocerca y detecta anomalías espacio-temporales antes de que ocurran la entrada o salida efectiva.

## 2. Definición del Problema
- Las reglas geofence reactivas tradicionales ejecutan acciones UEM *después* de que el dispositivo ha cruzado la frontera física o lógica.
- Los saltos imprevistos de país o zona (vía VPN o spoofing sofisticado) a menudo se evalúan únicamente como violaciones estáticas en el ciclo posterior.

## 3. Especificación Funcional
- **Detección de Cinemática Imposible**: Cálculo en Go de velocidad requerida entre puntos consecutivos (usando la fórmula del gran círculo de `internal/domain/geo`). Si $v > v_{max}$ (p. ej., >900 km/h en trayectos terrestres), asigna veredicto de alto riesgo (`risk_score >= 85`).
- **Score Predictivo de Frontera**: Evaluación de la trayectoria vectorial respecto a geocercas restringidas o corredores definidos en `internal/domain/route`. Emite un evento `approaching_restricted_zone` N minutos antes del impacto estimado.
- **Privacidad Local**: No conserva historiales de trayectorias exactas; solo almacena histogramas de velocidad y matrices de permanencia cifradas en `internal/store`.

## 4. Arquitectura de Implementación (Go / Local-First)
- **Subpaquete en Domain**: `internal/domain/chronos` (evaluador cinemático y estimación vectorial).
- **Integración con Risk**: Provee la señal pura `kinematic_anomaly` al agregador de `internal/domain/risk`.
