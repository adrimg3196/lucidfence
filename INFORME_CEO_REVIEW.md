# Informe CEO — Review Geofence UEM

**Veredicto:** Producto funcional y demo-comercial sólido, pero **el moat es más fino de lo que dice el marketing** y la propuesta "ejecuta acciones UEM automáticas" **no funciona out-of-the-box en live**. Vendible como servicio gestionado de una consultora, no como SaaS autónomo.

## 1. Propuesta de valor (clara)
Capa de política geoespacial que se sienta **sobre el UEM que ya tienes** (Applivery) y cierra el loop: detecta posición → puntúa riesgo 0-100 → decide por política explicable → ejecuta acción → notifica → audita. 100% local (sin exfiltrar datos), multi-tenant, ideal para compliance. Resuelve un hueco real: el UEM avisa, pero no actúa ni puntúa riesgo compuesto.

## 2. Ventaja industrial vs UEM genéricos (moat)
Real: el **Risk Engine compuesto** + **políticas auditables** (`policies.py`, ~120 LOC de pesos) y el enfoque compliance-local. Débil: esos pesos son arbitrarios (35 pts "fuera", 25 "no conforme"…), **sin calibración ni ground truth**. Un UEM (Intune/Jamf/Applivery) puede absorber geocercas+aviso en una sprint; la diferencia defendible es el empaquetado + venta como servicio, no la matemática.

## 3. Gaps que bloquean la venta
- **Ejecución real rota:** `actions.py` confirma que el endpoint de comandos de Applivery devuelve **404**; en live cae a `dry_run` + webhook a Zapier/Make que el cliente debe armar. La acción automática no es turnkey.
- **Latencia de 15 min:** polling cada 900 s mata el caso "anti-robo en tiempo real".
- **"SaaS" que no es SaaS:** corre en 127.0.0.1, sin facturación ni nube. Monetización "aparte" = indefinida. ¿Licencia blanca o MSP gestionado?
- **Posicionamiento inflado:** compararse con Fleet/Radar sin tracción daña credibilidad.
- **Dataset de zona de riesgo vacío** por defecto: señal clave del moat no aporta.

## 4. 3 mejoras priorizadas
1. **Cerrar el gap de ejecución (P0):** confirmar endpoint real de comandos Applivery o integrar vía API oficial documentada; si no, reposicionar honestamente como "orquestador que dispara tu SOAR" y **entregar la integración Zapier/Make pre-hecha**, no un webhook vacío. Sin acción real, es un dashboard.
2. **Calibrar el Risk Engine con 1 cliente real:** usar incidentes históricos como ground truth para los pesos y medir falsos positivos/negativos. Convierte el moat en defendible y da munición de venta.
3. **Definir modelo de entrega y precio:** elegir MSP gestionado vs licencia blanca, fijar €/dispositivo/mes, y quitar la contradicción "SaaS sin facturación" del pitch.
