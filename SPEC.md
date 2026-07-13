# SPEC — LucidFence Command Center

> Spec bloqueada antes de build. Ciclo: grill → spec → build → review (CEO/Eng/Design/DevEx) → QA → ship.
> Producto 100% local (macOS), multi-tenant, sin exfiltrar datos. Nada llega a "producción" (entregable cliente) sin pasar review + QA.

---

## 1. QUÉ ES

LucidFence es un **centro de mando local de geofencing para flotas móviles gestionadas por UEM** (MDM/EMM: Applivery, Intune, Jamf, Fleet).
Toma la ubicación que el agente del UEM reporta cada 15 min, la cruza con **geovallas** y **rutas comerciales**, y ejecuta **acciones UEM automáticas** (lock, wipe, message, locate, reboot, reset-passcode) cuando un dispositivo entra/sale de una zona, se desvía de su ruta, o cruza un umbral de riesgo.

Diferenciador (moat): no es "dibujar geocercas y avisar" (eso lo absorbe cualquier UEM en una sprint). El moat es el **Geospatial Risk & Policy Engine**: riesgo como función compuesta

    risk(device) = f(geofence_state, device_health, external_signals, time)

con señales externas pluggable (turno, hora, zona de riesgo, salud/root/encryption) y políticas compuestas explicablemente auditables.

## 2. PARA QUIÉN

- **IT / Seguridad de campo** de empresas con flota móvil dispersa (logística, retail, sanidad, fuerza de ventas, frontline industrial).
- **MSP / consultoras UEM** que quieren vender geofencing como servicio sobre Applivery.
- **CISO** que necesita auditoría de conformidad de dispositivos fuera de perímetro.

No es para: consumidor, ni para quien solo quiere "ver mapa". Es una herramienta de operación + auditoría.

## 3. VALOR / PROBLEMA QUE RESUELVE

- Un dispositivo fuera de su perímetro autorizado o desviado de ruta = riesgo (robo, fuga de datos, incumplimiento).
- Hoy el UEM avisa, pero no **actúa de forma policy-driven ni puntúa riesgo compuesto**.
- LucidFence cierra el loop: detecta → puntúa → decide → ejecuta acción UEM → notifica → audita.

## 4. MONETIZACIÓN (g-stack: "even good at monetisation")

Modelo SaaS multi-tenant local (ya implementado en `saas_server.py`):
- **Free**: 5 dispositivos, 3 geovallas, features básicas. (Demo que corre en 127.0.0.1.)
- **Pro**: flota ilimitada, políticas compuestas, SOAR/CVE, IA (MoA), alertas, export.
- **Enterprise**: multi-tenant, RBAC granular, audit log, integración live Applivery.

El producto ya tiene el esqueleto de planes (`/api/plan`, `/api/plan/upgrade`, limits por tenant). La monetización se realiza por el canal de venta de la consultora, no por el binario.

## 5. ALCANCE PRODUCTION-READY (lo que este ciclo debe dejar terminado)

Funciones IT que todo admin pide (ya implementadas en sesiones previas, validadas en navegador):
- [x] Geovallas + rutas + detección de transiciones
- [x] Acciones UEM automáticas (lock/wipe/message/locate/reboot/reset-passcode) con cooldown
- [x] Risk Engine compuesto (score 0-100) + políticas explicaples
- [x] Incidentes + MTTR + notificaciones (Slack/Teams)
- [x] Inventario de flota completo (SO, modelo, serial, batería, storage, usuario, depto, check-in)
- [x] Comandos remotos on-demand por dispositivo
- [x] Alertas configurables por umbral (6 tipos) + canales (email/Slack/none)
- [x] SOAR + CVE (inventario de apps vulnerables por dispositivo)
- [x] Workflows (plantillas + builder)
- [x] IA (MoA) integrada para preguntas en lenguaje natural sobre la flota
- [x] Export bulk/audit (CSV + HTML print-ready) de inventario/acciones/compliance
- [x] RBAC (owner/admin/operator/viewer) + multi-tenant isolation
- [x] Simulación realista sin credenciales + modo live con Applivery

Lo que ESTE ciclo debe cerrar para SHIP (entregable cliente):
1. SPEC formal (este doc).
2. Build: gaps de robustez/observabilidad para uso real.
3. Review 4 lentes (CEO/Eng/Design/DevEx) con informe de gaps.
4. QA real (suites + navegador + performance del ciclo).
5. SHIP: empaquetado (README ejecutivo, build/package, instrucciones de arranque para cliente).

## 6. NO ALCANCE (explícito, para no adivinar)

- No es un UEM: se apoya en el UEM existente (Applivery) para ejecutar acciones.
- No exfiltrra datos: todo en 127.0.0.1 / disco local.
- No incluye facturación real ni auth de terceros: el binario es la herramienta, la venta es aparte.
- No se publica a ningún registry/git: 100% local por política del cliente.

## 7. DEFINICIÓN DE HECHO (DoD)

- `python3 tests/run_tests.py` → 0 fallos.
- `python3 qa_saas.py` → 0 fallos.
- `python3 tests/test_it_admin_features.py` → 0 fallos.
- Dashboard carga en 127.0.0.1:8765, consola JS 0 errores, KPIs vivos.
- Comando remoto, alerta y export verificados end-to-end en navegador.
- Entregable empaquetado con README ejecutivo + instrucciones de arranque.
