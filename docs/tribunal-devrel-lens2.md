# TRIBUNAL DE MARKETING — LENS 2: DEVELOPER RELATIONS / COMUNIDAD

**Dictamen DevRel: cómo hacer open-source a Geofence UEM para atraer contribuidores y adoptantes**

**(1) ¿MDMAdapter es la superficie de contribución correcta?** SÍ, con un matiz. Es la superficie ideal porque es *bien delimitada, de alto valor visible y con baja dependencia del core*: alguien puede escribir el adapter de Jamf sin tocar el Risk Engine, los 115 tests ni el dashboard. Cumple la regla de oro de DevRel — "un PR de fin de semana". Riesgo real: si la interfaz no está congelada (contract), cada adapter rompe el core. Mantener la interfaz mínima (`fetch_devices`, `execute_action`, `get_health`) es lo que decide si engancha o ahuyenta.

**(2) Estructura a copiar de marketingskills (Corey Haines, 38k★/6.1k forks).** Llevar: `plugin.json` (manifest declarativo del adapter: vendor, auth, endpoints), `marketplace.json` (catálogo indexable con metadata de mantenimiento), `SKILL.md`→renombrar a `ADAPTER.md` (plantilla paso a paso para escribir un adapter), `.github/` (PR template que obligue a adjuntar test contra mock del vendor + `run_tests.py` en verde) y `CONTRIBUTING.md` con el "Adapter Dev Contract" (interfaz, convenciones, cómo entrar al registry). La lección de los 6.1k forks: empaquetar capacidades como unidades modulares + comunidad activa en issues = contribuidores.

**(3) El 'carrot' para escribir Intune/Jamf gratis.** No es dinero: es *estatus + utilidad propia*. Gamificar con "Adapter Hall of Fame" (crédito visible en README), dar co-maintainership al autor del primer adapter de un vendor grande, y — lo más fuerte — que el adapter resuelva su dolor real: quien usa Intune ya necesita geofencing; el adapter es su herramienta gratis a cambio de upstreamarlo. Bounties no monetarias (featured en doc, canal directo al core team) cierran el trato.

**(4) Riesgos de comunidad.** Fragmentación (N adapters de calidad desigual) y adapters rotos (el vendor cambia su API). Mitigar: CI obligatorio que ejecute los tests de cada adapter contra mocks; nivel de "certificación" (verified/community); deprecación automática si falla CI 2 releases seguidas; y un vendor oficial (Applivery) siempre como golden reference.

**3 recomendaciones DevRel:**
1. Congelar `ADAPTER.md` + `Adapter Dev Contract` y publicar un "starter adapter" (mock vendor) que corra los 115 tests — baja la barrera a un fork.
2. Lanzar "Adapter Bounty Sprint" (Jamf/Intune) con reconocimiento público, no dinero; al primer autor, co-maintainership.
3. Marketplace indexable + badge "verified" en README para combatir fragmentación y dar confianza al adoptante.
