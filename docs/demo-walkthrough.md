# Demo de LucidFence — lo que ves sin escribir código

 Esta demo te muestra LucidFence funcionando sin que instales nada ni escribas código. Puedes verlo todo desde el navegador.

## Paso 1 — Vitrina pública

Abre `https://adrimg3196.github.io/lucidfence/cloud.html` en tu navegador.

Eso carga el estado publicado de la vitrina: flota demo, geocercas, cumplimiento de compliance, riesgo geográfico y departamental. Todo lee `data/cloud_state.json` publicado en GitHub sin credenciales.

**Qué ver:**
- Dispositivos en la flota demo
- Estado de geocercas (dentro / fuera / no-compliant)
- Municipio de cada dispositivo
- Porcentaje de compliance

**No necesitas:** cuenta, token, instalación.

## Paso 2 — Dashboard local (opcional, si quieres probar en tu máquina)

```bash
# Clonar
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Correr el servidor (sin Docker, Python directo)
python3 saas_server.py
```

Abre `http://localhost:8765` — dashboard local con la misma información de la vitrina, pero corriendo en tu máquina con tus propios datos.

**Qué ver:**
- Mismo dashboard que la vitrina, pero con tus datos
- Panel de flota, geocercas, compliance
- Logs del engine

## Paso 3 — Ver los tests (opcional, para confiar en que funciona)

```bash
python3 tests/run_tests.py
```

El runner honesto corre los tests contra mock. Suite en verde = engine, auth, adapters, policies funcionando según lo declarado. (El tally exacto vive en CI; los números en prosa caducan.)

**No necesitas:** UEM real, credenciales, datos de producción.

## Paso 4 — Ver el adaptador Intune (si quieres ver integración real)

El adaptador Intune está verificado contra Microsoft Graph. Puedes ver el código:

```bash
cat lucidfence/core/adapters/intune.py
```

Y los tests:

```bash
cat tests/test_adapters_intune_live.py
```

## Paso 5 — Ver el adaptador Jamf (si quieres ver integración real)

El adaptador Jamf está verificado contra Jamf Pro API.

```bash
cat lucidfence/core/adapters/jamf.py
cat tests/test_adapters_jamf_live.py
```

## Paso 6 — Ver el engine de geofencing

El engine es lo que ejecuta la lógica de geocercas + políticas de riesgo:

```bash
cat lucidfence/core/engine.py
```

## Paso 7 — Ver cómo se publica la vitrina

El flujo completo:

```bash
cat lucidfence/core/cloud_publisher.py
cat .github/workflows/engine-cron.yml
```

El engine-cron corre cada 15 min en GitHub Actions, construye la flota demo, corre el engine, y publica `data/cloud_state.json` que la vitrina lee.

## Paso 8 — Ver cómo instalar (sin el servidor, solo el código)

Si quieres instalar LucidFence en tu infra:

```bash
cat docker-compose.yml
cat Dockerfile
```

O lee la guía de arranque completa en [docs/GETTING_STARTED.md](GETTING_STARTED.md).

## Qué NO hace esta demo

- No crea tenants reales en tu nombre (eso es el SaaS self-service del issue/PR flow)
- No ejecuta comandos contra dispositivos reales (eso requiere credenciales UEM)
- No expone datos de producción (eso es tu responsabilidad, BYOI)

## Próximos pasos

- Para contribuir: `CONTRIBUTING.md`
- Para agregar un adaptador UEM nuevo: `docs/contributing/new-adapter-guide.md`
- Para reportar un bug: abre un issue con la plantilla `bug_report`
- Para seguridad: `SECURITY.md`

---

*Vitrina actualizada cada 15 min por engine-cron. Última actualización: ver `data/cloud_state.json` en el repo.*
