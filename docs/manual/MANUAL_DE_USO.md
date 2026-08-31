# Manual de Uso — LucidFence

Guía completa para administradores de LucidFence.

## Requisitos previos

- Python 3.11+
- Acceso a al menos un platform UEM (Applivery, Intune, Jamf, Fleet)
- Acceso de terminal en macOS, Linux o Windows

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -e .

# Verificar instalación
lucidfence --version
```

## Primeros pasos

### Paso 1: Inicializar configuración

```bash
lucidfence init
```

Esto crea un archivo `config.json` con valores por defecto.

### Paso 2: Configurar un proveedor UEM

Edita `config.json` para añadir las credenciales de tu proveedor:

```json
{
  "mode": "dry_run",
  "applivery": {
    "api_key": "tu-api-key",
    "org_id": "tu-org-id"
  }
}
```

### Paso 3: Arrancar el servidor

```bash
lucidfence server
```

Abre http://localhost:8765 en tu navegador.

### Paso 4: Verificar que funciona

Ve a **Settings → Providers** y conecta tu proveedor UEM. Verás los dispositivos en el panel **Devices**.

## Uso diario

### Sincronización

```bash
# Sincronización manual
lucidfence sync

# Sincronización forzada
lucidfence sync --force

# Sincronización en modo dry-run (sin efectos secundarios)
lucidfence sync --dry-run
```

### Gestión de políticas

```bash
# Listar políticas
lucidfence policies list

# Validar políticas
lucidfence policies validate

# Exportar políticas
lucidfence policies export > policies.json
```

### Gestión de geocercas

```bash
# Listar geocercas
lucidfence fences list

# Crear geocerca
lucidfence fences create --name "Oficina Madrid" --latitude 40.4168 --longitude -3.7038 --radius 500

# Eliminar geocerca
lucidfence fences delete --name "Oficina Madrid"
```

## Panel de control

### Vista general

Muestra el estado de tu flota:

- Dispositivos totales
- Dispositivos dentro de geocercas
- Dispositivos fuera de geocercas
- Estado de compliance
- Incidentes recientes

### Dispositivos

Lista de todos los dispositivos de tus proveedores UEM:

- Nombre, ID, plataforma
- Ubicación actual (si disponible)
- Estado dentro/fuera de geocercas
- Estado de compliance
- Última sincronización

Haz click en un dispositivo para ver detalles.

### Geocercas

Tus geocercas definidas y su estado:

- Lista de todas las geocercas
- Dispositivos dentro/fuera de cada una
- Historial de violaciones
- Crear/editar/eliminar geocercas

### Incidentes

Timeline de eventos activados por políticas:

- Cuándo y qué ocurrió
- Qué dispositivo y política
- Acciones tomadas
- Nivel de severidad

## Configuración avanzada

### Modo de enforcement

- **Observe**: solo logging, sin acciones
- **Enforce**: toma acciones configuradas (bloquear, bloquear, wipe, etc.)

Empieza siempre en modo **observe**. Cambia a **enforce** solo después de probar.

### Variables de entorno

Puedes usar variables de entorno para credenciales sensibles:

```bash
export APPLIVERY_API_KEY="tu-key"
export APPLIVERY_ORG_ID="tu-org"
lucidfence server
```

### Calendario de sincronización

Por defecto, la sincronización ocurre cada 5 minutos. Puedes configurar el intervalo en `config.json`.

## Solución de problemas

### El panel no carga

1. Verifica que el servidor esté ejecutándose: `lucidfence server`
2. Revisa los logs del servidor
3. Prueba con otro navegador o modo incógnito

### No aparecen dispositivos

1. Verifica que al menos un proveedor UEM esté configurado
2. Ve a Settings → Providers y verifica la conexión
3. Espera a la primera sincronización (puede tomar 30-60 segundos)

### Credenciales no funcionan

1. Verifica que tu API key/token sea correcta
2. Verifica que las credenciales tengan los permisos necesarios
3. Revisa los incidentes para ver detalles de error de auth

## Seguridad

- LucidFence es **local-first**: tus credenciales y datos de dispositivos nunca salen de tu máquina sin tu consentimiento explícito.
- El publishing opcional de `cloud_state.json` para la vitrina GitHub Pages usa solo datos demo/sintéticos.
- Para reportar vulnerabilidades, ver `SECURITY.md`.

## Estado del producto

LucidFence es **open-source 100% free (Apache-2.0)**. Sin pricing, sin enterprise edition, sin funciones de pago, sin telemetría.

## Documentación relacionada

- [Getting Started](./getting-started.md) — Guía para nuevos usuarios
- [Referencia POLICY DSL](../reference/POLICY_DSL.md) — Referencia del lenguaje de políticas
- [Soporte y contribuciones](../contributing/) — Cómo contribuir
