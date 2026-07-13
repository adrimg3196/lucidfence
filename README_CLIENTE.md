# Geofence UEM — Guía de arranque (para el cliente)

Centro de mando local de **geofencing para flotas móviles gestionadas por UEM** (Applivery/Intune/Jamf/Fleet).
100% local en macOS: nada sale de tu máquina. Dashboard en http://127.0.0.1:8765

---

## 1. Arranque (un solo comando)

```bash
cd /ruta/a/geofence-uem
./start_all.sh
```

Esto levanta dos servicios locales:
- **Geofence UEM** en http://127.0.0.1:8765  ← el dashboard
- **MoA (IA)** en http://127.0.0.1:8085       ← motor de preguntas en lenguaje natural

Al terminar, el script reporta `✓ MoA arriba` y `✓ Geofence arriba` y la URL del dashboard.

> Sin claves de IA configuradas, MoA funciona en **modo demo** (respuestas sintéticas).
> Para IA real, añade una clave (p.ej. Groq) en `/Users/adri/moa/.env` y reinicia.

## 2. Abrir el dashboard

Abre en el navegador: **http://127.0.0.1:8765**

El login demo es automático (sesión local de solo-lectura/operación). Para crear tu propia organización:
usa **Registrarse** en la pantalla de login.

## 3. Qué puedes hacer (vista rápida)

| Vista | Para qué |
|-------|----------|
| **Resumen** | KPIs de flota: dispositivos, dentro/fuera, incumplimientos, CVE |
| **Mapa** | Posición en vivo de cada dispositivo vs geovallas |
| **Dispositivos** | Lista operativa con estado de conformidad |
| **Inventario** | Activos IT: SO, modelo, serial, batería, almacenaje, usuario, depto |
| **IA · MoA** | Pregunta en lenguaje natural: *"¿Qué dispositivo incumple y por qué?"* |
| **Eventos / Incidentes** | Traza y MTTR de incidencias de perímetro |
| **SOAR · CVE** | Playbooks y vulnerabilidades por app/dispositivo |
| **Acciones** | Log de acciones UEM ejecutadas (lock/wipe/locate…) |
| **Alertas** | Umbrales configurables (batería, fuera de geovalla, riesgo…) + Slack/email |
| **Geovallas / Rutas** | Define perímetros y rutas comerciales |
| **Workflows** | Automatizaciones (plantillas + builder) |
| **Objetivos** | KPIs de operación |
| **Ajustes** | Token de Applivery (modo live), webhook de incidentes |

### Comandos remotos on-demand
Abre cualquier dispositivo (botón **Ver**) → panel **COMANDOS REMOTOS (MDM/UEM)**:
🔒 Bloquear · ⚠️ Borrar · 📍 Localizar · 🔄 Reiniciar · 🔑 Reset PIN · 💬 Mensaje.

### Export / Auditoría
En **Inventario**: botones **CSV · PDF · Compliance CSV · Acciones CSV** para sacar
reportes auditables (el "PDF" es un reporte HTML imprimible — en el navegador: Imprimir → Guardar como PDF).

## 4. Parar / estado

```bash
./start_all.sh status   # muestra si ambos servicios están vivos
./start_all.sh stop     # detiene ambos
```

## 5. Modo live (con Applivery real)

En **Ajustes**, pega tu `APPLIVERY_API_KEY`. El producto pasa de simulación a
**live** y empieza a leer la ubicación real de tu flota vía la API del UEM.

## 6. Requisitos

- macOS con Python 3.9+
- Una dependencia externa: `requests`  (`pip install -r requirements.txt`)
- Nada más. Sin cuenta en la nube, sin exfiltrar datos.

## 7. Tests / QA (para el equipo técnico)

```bash
python3 tests/run_tests.py              # 71 tests core
python3 qa_saas.py                      # 19 tests SaaS
python3 tests/test_it_admin_features.py # 25 tests de funciones IT
```

---

_Documento de arranque para el cliente. El producto es 100% local por política; no se publica a ningún registry._
