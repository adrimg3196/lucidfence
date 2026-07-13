---
name: geofence-setup
description: Cómo arrancar el producto Geofence UEM en local (./start_all.sh), qué levanta y cuándo usarlo. Usa cuando el usuario quiere iniciar el dashboard, poner en marcha el servidor, probar en modo demo/simulación, o verificar que Geofence UEM está corriendo.
---

# Geofence UEM — Arranque local

Geofence UEM es un **dashboard local de geofencing para flotas UEM**, 100%
funcional en macOS, multi-tenant, que acciona acciones automáticas (lock, wipe,
message, locate, reboot) cuando un dispositivo entra/sale de una geovalla. Hoy
funciona con Applivery; es extensible a Intune/Jamf/Fleet vía adaptadores
`MDMAdapter`.

## Qué hace `./start_all.sh`

Levanta dos servicios en background y verifica su salud:

- **MoA** en `http://127.0.0.1:8085` — capa de mezcla de modelos de IA
  (opcional; usa modo DEMO/mock si no hay claves de proveedor).
- **Geofence UEM** en `http://127.0.0.1:8765` — el dashboard y motor de
  geofencing (arranca `saas_server.py`).

Al final reporta el estado de las claves de IA (solo presencia, nunca el valor)
y la URL del dashboard.

## Cuándo usarlo

- Primera vez que vas a usar el producto o tras reiniciar la máquina.
- Para probar el flujo de geovallas sin credenciales: arranca en **modo
  simulación** (flota sintética que se mueve entre waypoints). No necesitas
  `APPLIVERY_API_KEY`.
- Para pasar a **modo live**: define `APPLIVERY_API_KEY` (o las credenciales del
  MDM correspondiente) y reinicia.

## Cómo arrancar

```bash
cd /Users/adri/geofence-uem
./start_all.sh            # arranca MoA + Geofence en background
./start_all.sh status     # muestra estado de ambos puertos
./start_all.sh stop       # detiene ambos servidores
```

Tras `./start_all.sh`, abre: **http://127.0.0.1:8765/**

## Verificación de salud

El script consulta `http://127.0.0.1:<puerto>/api/health` y busca
`"status": "ok"`. Si alguno no arranca, revisa los logs:

- Geofence: `logs/geofence.log`
- MoA: `logs/moa.log`

## Modo DEMO vs IA real

Si no hay ninguna clave de proveedor (Groq, OpenRouter, NVIDIA, DeepSeek,
Cerebras, Mistral, GitHub Token, HF, Gemini) en el `.env` de MoA, la IA corre en
**modo DEMO (mock)**. Añade al menos una clave y reinicia para usar IA real en
la mezcla MoA.

## Notas

- El script instala `requests` automáticamente si falta.
- No ejecuta acciones reales contra dispositivos en modo simulación.
- No toques `core/` ni `saas_server.py` para arrancar; solo usa este script.
