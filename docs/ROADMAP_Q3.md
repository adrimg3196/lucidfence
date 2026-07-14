# Roadmap Q3 2026 — LucidFence

> Priorizado por PM (task `t_e98013c5`). Backlog fuente: board `uem-ops`.
> Estado producto: vitrina demo viva (GitHub Pages + `saas_server.py` local :8765),
> self-service multi-tenant ya funciona vía GitHub Issues (sin token del usuario),
> y feed CVE/SOAR en vitrina hoy muestra "(datos demo)".

## Premisa
Pasar de "demo técnica" a "máquina comercial autónoma": cerrar el ciclo
prospect → tenant → vitrina → cierre, con credibilidad de seguridad real
(CVE en vivo) y un path claro a despliegue internet-facing (Fly) sin exponer secretos.

## Principio de priorización
1. **Gating de seguridad antes** de cualquier exposición internet-facing (Fly).
2. **El bucle comercial** (self-service + landing) es el que genera pipeline →
   máxima prioridad tras el gate.
3. **Credibilidad** (CVE real, competitive intel) habilita ventas enterprise.
4. **Pulido de vitrina y cobertura de plataformas** es Wave 3 (no bloquea ingresos).

## Secuencia

### Wave 1 — Exponer sin riesgo (Semanas 1-2)
| P | Task | ID | Qué entrega |
|---|------|----|-------------|
|100| Seguridad M1/M2 | `t_337c12e1` | TLS + verificación de deps en `install.sh`. **GATE para Fly.** |
| 95| Self-service E2E | `t_33fdd4f8` | Validar issue→tenant→vitrina con tenant real; SLA ≤15 min documentado. |
| 90| Landing conversión | `t_ec2b704e` | Testimonios + pricing tiers + FAQ instalación; alimenta el self-service. |

### Wave 2 — Credibilidad comercial (Semanas 3-4)
| P | Task | ID | Qué entrega |
|---|------|----|-------------|
| 80| CVE feed real NVD | `t_1ec8c6e6` | Quita el badge "(datos demo)"; fallback demo si no hay red. |
| 75| Competitive intel | `t_1fea954e` | Battlecard LucidFence vs Jamf/Intune/Applivery. |
| 70| Installer systemd | `t_5b7f6139` | Always-on para clientes self-host (entrega del modelo soberano de pago). |
| 65| Seguridad M3/M4 | `t_2bcaf6bf` | Rate-limit login + errores 500 genéricos (hardening post-public). Depende de M1/M2. |

### Wave 3 — Vitrina & cobertura (Semanas 5-6)
| P | Task | ID | Qué entrega |
|---|------|----|-------------|
| 55| Vitrina heatmap | `t_82a36438` | Mapa de calor por departamento + filtro tenant. |
| 50| ChromeOS | `t_14d224a8` | Plataforma en seed + vitrina. |
| 45| Monitor SLA | `t_eedc0704` | Health-check que abre tareas de fix si tests<110 o vitrina caída. |

### Backlog (fuera de Q3 comprometido)
| P | Task | ID |
|---|------|----|
| 30| Doc runbook Obsidian | `t_24a35bc9` |
| 25| Apple geofence adapter | `t_0cd99deb` |
| 20| Windows compliance policy | `t_c2ecde2f` |
|  5| Higiene board (27 daily scans bloqueados stale) | `t_a307d934` |

## Notas PM / decisiones
- **Umbral del monitor es frágil**: hoy hay exactamente 110 tests; el monitor
  salta si `tests<110`. Recomiendo cambiar a "tests < 100 O caída >5% vs baseline"
  para evitar falsos positivos al crecer la suite.
- **Self-service y landing NO dependen de Seguridad**: corren sobre GitHub Pages /
  Actions, no exponen el server. Seguridad solo gatea el deploy Fly internet-facing,
  que es un paso comercial posterior.
- **Fly deploy sigue requiriendo acción humana**: el usuario debe correr
  `flyctl auth login` en su terminal (el agente no puede hacer login headless).
  Seguridad M1–M4 es prerequisito, no suficiente.
- **27 daily scans en `blocked` desde 2026-07-04** están stale (sin comentario de
  bloqueo ni evento de block). Se creó `t_4b1c2d3e` para archivarlos limpiamente.
