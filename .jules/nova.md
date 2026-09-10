# Registro de Descubrimiento NOVA y Lecciones de Diseño

## Principios Inviolables para el Desarrollo por Hermes

Cuando Hermes aborde la implementación de las propuestas del horizonte EXPLORE, debe mantener los siguientes principios rectores de LucidFence 2.0:

1. **Local-First Sin Excepciones**: Ninguna función (incluyendo modelos predictivos o consorcios P2P) debe depender de servidores externos, servicios cloud o APIs de terceros. Todo el cómputo debe realizarse en la máquina o dispositivo local.
2. **Cero Telemetría y Privacidad Estricta**: La ubicación del usuario no sale del entorno del tenant.
3. **Módulo Único Go**: Toda nueva capacidad del motor de riesgo o geofencing debe residir dentro de `internal/domain/...` como paquetes puros Go sin efectos secundarios ni I/O.
4. **Cumplimiento Normativo de Arquitectura**: Respetar los límites físicos definidos en `ARCHITECTURE.md` (ficheros Go ≤ 400 líneas, funciones ≤ 60 líneas, complejidad ciclomática ≤ 15).
5. **Verificabilidad Batería Runtime**: Toda nueva funcionalidad debe añadir sus correspondientes checks de verificación en vivo en `internal/battery`.

## Hoja de Ruta para Hermes

Las 6 propuestas registradas en `docs/product/nova-visionary-features.md` y `docs/roadmap/PRODUCT_ROADMAP.md` están listas para ser priorizadas y convertidas progresivamente en código Go, manteniendo la máxima elegancia, rendimiento y seguridad.
