# LucidFence — Estrategia de Comunidad & Programa de Adapters

*Generado con skill `community-marketing` + dictamen DevRel del tribunal.*
*Identidad del community: "MSPs y devs que se niegan a subir la ubicación de su flota a la nube y quieren un plano de control agnóstico a MDM".*

---

## 1. Identidad (no es "usuarios de LucidFence")

Comunidad de **self-hosters UEM soberanos + MSPs multi-MDM**. Se quedan por la identidad: "controlo mi flota sin vendor lock-in de nube". Modelo: r/homelab pero para UEM.

## 2. El carrot para escribir adapters (Intune/Jamf gratis)

Del DevRel: el carrot NO es dinero. Es:
- **Utilidad propia**: el adapter resuelve SU dolor real (su MDM no está agregado).
- **Estatus + co-maintainership**: "Adapter Maintainer" en el Hall of Fame del README.
- **Badge "verified"** en el marketplace de adapters.
- **Influencia en roadmap**: los maintainers entran al canal privado de diseño de la interfaz.

## 3. Programa "Adapter Bounty Sprint"

- Sprint de 2 semanas al lanzar: recompensa pública (Hall of Fame + shoutout en LinkedIn) al primer adapter verificado de Intune y de Jamf.
- Plantilla `ADAPTER.md` + starter adapter mock que pasa los 115 tests (baja la barrera a "PR de fin de semana").
- CI obligatorio: todo adapter PR debe pasar tests contra mock + lint. Badge "verified" automático al merge.

## 4. Arquitectura de canales (pre-lanzamiento → crecimiento)

| Canal | Propósito | Etapa |
|-------|----------|-------|
| GitHub Discussions | Soporte técnico, pedidos de adapter, RFC de interfaz | always |
| Discord (dev) | Tiempo real, adapters, debugging | crecimiento |
| LinkedIn (MSP) | Casos MSP, demos, Hall of Fame | always |
| r/selfhosted + Jamf Nation + foros Intune | Adquisición (land via MSP) | lanzamiento |

## 5. Flywheel

```
MSP forkea → instala adapter de su MDM → lo manda a su cliente
   → cliente pide otro MDM → MSP abre PR de adapter → se vuelve maintainer
   → recomienda LucidFence a otro MSP (word-of-mouth)
```

## 6. Rituales

- **Semanal**: "Adapter of the Week" (shoutout al merge verificado).
- **Mensual**: AMA con el equipo core sobre la interfaz MDMAdapter.
- **Lanzamiento**: "Adapter Bounty Sprint" con tabla pública de progreso.

## 7. Métricas de salud (Growth OKR)

- adapters MDM contribuidos (salud de la comunidad) → meta Q1: 5
- forks (embedding en flotas reales) → meta Q1: 200
- stars (awareness) → meta Q1: 2.000
- leads MSP (negocio) → meta Q1: 10 demos

## 8. Anti-patrones a evitar

- Prometer "cualquier MDM" sin ≥2 adapters reales (vaporware).
- Adapters rotos en main: CI obligatorio + deprecación automática con aviso.
- Comunidad solo de la empresa: objetivo ≥70% de posts de no-staff en Discussions.

---
*Siguiente: skill `launch` para el plan de GTM con estos canales y el Bounty Sprint como evento de apertura.*
