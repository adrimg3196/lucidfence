# ADR-0001 — Servidor HTTP stdlib, sin Flask/FastAPI

**Estado:** Accepted — ~2026-07 (identidad fundacional; reafirmado con la Constitución 2026-08-20).

## Contexto

LucidFence sirve dashboard, API y engine loop desde un único proceso Python que
el cliente corre en su propia máquina. Un framework web (Flask, FastAPI) traería
Werkzeug/Starlette, Pydantic, uvicorn y su árbol transitivo: decenas de
dependencias que hay que auditar, fijar en `requirements.lock` y mantener al día,
en un producto cuya promesa es "corre en tu máquina, sin sorpresas". La API es
modesta (rutas JSON, RBAC, un webhook firmado, un gateway OpenAI-compatible), no
justifica el peso ni la superficie de un framework.

## Decisión

El HTTP del producto se implementa sobre `http.server` de la stdlib. Todo el
servidor vive en `saas_server.py` (más `server.py` para el modo local básico).
Ninguna dependencia web entra en el runtime: añadirla es una decisión de
arquitectura que exige un ADR nuevo, no un `import`.

## Consecuencias

- **A favor:** cero frameworks web que auditar o parchear; instalación mínima;
  el comportamiento HTTP es legible sin conocer un framework; arranca con
  `python3 saas_server.py` y nada más.
- **En contra:** enrutado, parsing y validación se escriben a mano; `saas_server.py`
  es grande y concentra mucha superficie; features que un framework regala
  (OpenAPI auto, validación declarativa) se mantienen a mano (`openapi.json`
  vive junto a la spec y se actualiza con cada cambio de rutas).
- **Métrica de guardia:** 0 frameworks web añadidos.

## Dónde vive hoy

`saas_server.py` (HTTP stdlib propio), `server.py`; principio en
[CONSTITUTION.md §V stdlib-first](../architecture/CONSTITUTION.md); mapa en
[SPEC.md §3/§5](../architecture/SPEC.md).
