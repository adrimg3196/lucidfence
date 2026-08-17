# Geofencing lógico por red (portátiles / Windows sin GPS)

Los portátiles gestionados (Intune, Fleet/osquery) casi nunca traen GPS: no hay
CoreLocation ni chip de posición, y las APIs de UEM tampoco dan un stream de
ubicación de flota (ver [LOCATION_MATRIX.md](LOCATION_MATRIX.md)). Lo que un
administrador de IT **sí** conoce es la topología de su red: "nuestro bloque de
IP de salida es la sede", "la SSID `CORP-MADRID` es la oficina de Madrid", "esta
BSSID es el AP de la sala de servidores".

El **geofencing lógico por red** convierte ese conocimiento —declarado por el
operador— en una ubicación **gruesa y honesta** que el motor de riesgo correlaciona
igual que cualquier otra fuente. Es lo que la matriz de ubicación llamaba
"aproximada por señal de red (IP pública, SSID/BSSID)"; este documento es el
mecanismo concreto.

## Qué es y qué NO es

- **Es**: un mapeo local `firma de red → sitio con nombre y coordenadas`. Si el
  dispositivo sale a internet por un bloque de IP declarado, o está conectado a
  una SSID/BSSID declarada, el motor lo ubica en ese sitio.
- **No es** GPS. Un portátil sin GPS nunca dará radios de 200 m. La precisión
  que se declara (`accuracy_m`) es el **radio del sitio** — típicamente cientos
  de metros o el campus entero. Sirve para "¿está en la red de la oficina / en
  qué país sale a internet?", no para radios finos.
- **No llama a terceros.** No hay geoip comercial, ni MaxMind, ni ninguna
  petición de red. La ubicación sale ÚNICAMENTE de tu mapeo. La señal de red de
  tu flota jamás abandona tu máquina — garantía de diseño, no de marketing.

## Configuración

Declara los sitios bajo la clave `network_sites` en la config del tenant. Cada
sitio lleva un nombre, sus coordenadas + radio, y una o más firmas de red:

```json
{
  "network_sites": [
    {
      "name": "Sede Madrid",
      "lat": 40.4168,
      "lng": -3.7038,
      "radius_m": 600,
      "ip_cidrs": ["198.51.100.0/24", "203.0.113.0/24"]
    },
    {
      "name": "Sala de servidores",
      "lat": 40.4170,
      "lng": -3.7035,
      "radius_m": 30,
      "bssids": ["aa:bb:cc:dd:ee:ff"],
      "ssids": ["CORP-INFRA"]
    }
  ]
}
```

- `ip_cidrs`: rangos de IP de **salida** (la IP pública con la que el dispositivo
  aparece en internet), en notación CIDR. Se admite IPv4 e IPv6, y bits de host
  (p. ej. `203.0.113.5/24`).
- `ssids`: nombres de red Wi‑Fi. Comparación exacta, insensible a mayúsculas.
- `bssids`: MAC del punto de acceso. Se normaliza (minúsculas, `:` o `-`).

Sin `network_sites` declarados, la función es **inerte**: el comportamiento del
producto es idéntico a como si no existiera.

## Precedencia (cuando varias firmas casan)

Determinista, documentada y probada:

1. **Clase de señal, de la más específica a la menos**: un match por **BSSID**
   (un AP concreto) gana a un match por **SSID** (una red Wi‑Fi), que gana a un
   match por **CIDR de IP** (un bloque de salida).
2. **Dentro de la misma clase**: gana el sitio con `radius_m` **más pequeño** (el
   más específico geográficamente).
3. **Desempate final**: orden alfabético por nombre de sitio.

## Cómo se correlaciona

El resolver se conecta en la capa de fuente de ubicación
(`lucidfence/core/network_location.py` + `location_source.py`): si un report llega
**sin coordenadas usables** y sus señales de red casan con un sitio, se rellena
con `lat/lng` del sitio, `accuracy_m == radius_m` y `location_source="network"`.
A partir de ahí es un fix como cualquier otro para el motor de geocercas.

## Reglas de producto que protegen al admin

- **Nunca se inventa una ubicación.** Si ninguna firma configurada casa, el
  dispositivo se queda `unknown` — nunca se le asigna una posición por defecto.
- **Nunca sobreescribe un fix real.** Si el report ya trae GPS (p. ej. vía
  Applivery o el adapter iOS), el enriquecimiento por red no lo toca.
- **Precisión honesta.** Como `accuracy_m` es el radio del sitio, una política
  que exija precisión fina antes de actuar se negará correctamente sobre un fix
  grueso (ver la regla de `accuracy_m` en [LOCATION_MATRIX.md](LOCATION_MATRIX.md)).
- **Fail‑closed.** Señales o sitios malformados (IP basura, BSSID corta, radio
  negativo) nunca lanzan ni fabrican una ubicación: simplemente no casan. Los
  sitios inválidos se descartan al construir el resolver, no rompen los válidos.

## Relacionado

- [LOCATION_MATRIX.md](LOCATION_MATRIX.md) — qué ubicación da de verdad cada UEM.
- [FLEET.md](FLEET.md) — Fleet/osquery como recolector de evidencia y postura.
- [OSQUERY.md](OSQUERY.md) — postura de endpoint por osquery (disco, cifrado, OS).
