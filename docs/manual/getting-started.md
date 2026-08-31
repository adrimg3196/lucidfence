# Getting Started — LucidFence

Guía para nuevos usuarios que instalan LucidFence por primera vez.

## Qué necesitas

- Python 3.11+
- Un proveedor UEM (Applivery, Intune, Jamf, o Fleet) con credenciales de API
- Un terminal (macOS, Linux, o Windows)

## Instalación rápida

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Verificar que funciona

```bash
lucidfence --version
lucidfence quickstart
```

`quickstart` te guía paso a paso: entorno → app → dashboard → fuente de datos.

## Conectar tu UEM

1. Ve a **Settings → Providers** en el dashboard
2. Añade tu proveedor (Applivery, Intune, Jamf, Fleet)
3. Introduce las credenciales API
4. Verifica que los dispositivos aparecen en el panel **Devices**

## Primer paso real

Crea una geocerca simple:

1. Ve a **Geofences → New**
2. Ponle nombre (ej. "Oficina")
3. Pon las coordenadas y radio
4. Guarda

Verás los dispositivos entrando/saliendo en **Incidents**.

## FAQ

**¿Por qué no veo dispositivos?**
- Espera a la primera sincronización (30-60 segundos)
- Verifica que las credenciales son correctas
- Revisa **Settings → Providers** para el estado de conexión

**¿Puedo usar solo un UEM?**
Sí. No necesitas todos los proveedores. Uno es suficiente para empezar.

**¿Es seguro?**
Sí. LucidFence es local-first: tus credenciales y datos de dispositivos nunca salen de tu máquina sin tu consentimiento explícito. No hay backend propietario.

**¿Cuánto cuesta?**
Nada. LucidFence es 100% free y open-source (Apache-2.0). Sin pricing, sin enterprise, sin funciones de pago.

## Reportar bugs

Abre un issue en GitHub: https://github.com/adrimg3196/lucidfence/issues

Para seguridad, ver `SECURITY.md`.

## ¿Necesitas ayuda?

- [Manual de Uso](./MANUAL_DE_USO.md) — Documentación completa
- [Referencia POLICY DSL](../reference/POLICY_DSL.md) — Lenguaje de políticas
- [Contribuir](../contributing/) — Cómo contribuir al proyecto
