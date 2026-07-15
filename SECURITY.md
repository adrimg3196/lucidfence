# Security Policy

## Versiones soportadas

La última release estable recibe correcciones de seguridad. Las versiones anteriores deben actualizarse antes de solicitar soporte.

## Reportar una vulnerabilidad

No abras un issue público con detalles explotables, credenciales, datos de dispositivos o información de tenants.

Usa un [GitHub Security Advisory privado](https://github.com/adrimg3196/lucidfence/security/advisories/new) e incluye:

- versión y plataforma;
- impacto y escenario de amenaza;
- pasos mínimos de reproducción;
- logs sanitizados, sin tokens ni datos personales;
- propuesta de mitigación, si la tienes.

Se confirmará la recepción en cuanto sea posible. La corrección y divulgación se coordinarán de forma responsable antes de publicar detalles.

## Alcance de seguridad local

LucidFence escucha en `127.0.0.1` por defecto y guarda estado en el perfil del usuario. No expongas el servicio a una red sin firewall, autenticación y reverse proxy TLS. Nunca subas `.env`, credenciales UEM, sesiones ni directorios de Application Support a Git.
