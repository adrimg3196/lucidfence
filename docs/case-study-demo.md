# Caso de uso verificable — flota logística demo

> Este es un caso demostrativo reproducible, no un testimonial de cliente. No se
> atribuyen resultados a terceros sin autorización y evidencia.

## Contexto

Una empresa logística necesita detectar salidas de perímetro, priorizar riesgo
por CVE/compliance y ejecutar remediaciones UEM sin enviar telemetría a un SaaS.
La demo incluida representa 6 dispositivos multi-plataforma y tres geovallas.

## Recorrido reproducible

1. Ejecutar `./bin/lucidfence start --no-open`.
2. Abrir `http://127.0.0.1:8765/` y usar el acceso demo local.
3. Forzar varios ciclos desde “Ciclo”.
4. Revisar “Inteligencia”: calidad de señal, anomalías GPS y riesgo de cruce.
5. Revisar “SOAR·CVE”: CVEs correlacionados y playbooks explicables.
6. Exportar compliance/incident CSV o PDF desde el Command Center.

## Evidencia y métricas

- El engine de simulación produce datos reales del motor, no capturas estáticas.
- Cada score de riesgo incluye razones y procedencia.
- La predicción de movimiento es extrapolación local de corto horizonte; expone
  observaciones, ventana, velocidad, confianza y limitaciones.
- Las acciones destructivas respetan dry-run, deduplicación y cooldown.
- Los tests HTTP comprueban aislamiento tenant y RBAC.

## Criterio de éxito de piloto

- Instalación a primera flota en menos de 5 minutos.
- Cero datos del tenant fuera de su infraestructura.
- Cero errores de consola y todos los endpoints de cada vista con datos válidos.
- Incidente crítico trazable desde señal → score → playbook → auditoría.

## Cómo sustituir la demo por un caso real

Con consentimiento escrito del cliente, registrar únicamente métricas agregadas:
tiempo de detección, reducción de falsos positivos, tiempo de remediación y
porcentaje de flota cubierta. Nunca publicar nombres, ubicaciones, tokens o
identificadores de dispositivos. Un testimonial requiere aprobación explícita.
