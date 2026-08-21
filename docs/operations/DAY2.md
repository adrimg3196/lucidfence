# Día 2: operar LucidFence en producción

Instalar es el día 1. Esto es lo que un admin necesita para el resto:
arranque como servicio, backup, upgrade, cadencia de polling y monitorización.

## Arranque como servicio

**macOS (Homebrew):**

```bash
brew install adrimg3196/lucidfence/lucidfence
brew services start lucidfence      # launchd: sobrevive reinicios
# logs: $(brew --prefix)/var/log/lucidfence.log
```

**Linux (systemd):** crea `/etc/systemd/system/lucidfence.service`:

```ini
[Unit]
Description=LucidFence Command Center (local-first)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lucidfence
Environment=LUCIDFENCE_DATA_DIR=/var/lib/lucidfence
# Credenciales UEM por EnvironmentFile, nunca en la unit ni en YAML:
EnvironmentFile=-/etc/lucidfence/env
WorkingDirectory=/opt/lucidfence
ExecStart=/usr/bin/python3 /opt/lucidfence/lucidfence/cli.py serve --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5
# Endurecimiento básico
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/lucidfence
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now lucidfence
```

**Docker:** `docker compose up -d` con el `docker-compose.yml` del repo
(monta un volumen en el data dir para que los datos sobrevivan al contenedor).

## Backup y restore

Todo el estado vive en el **data dir** (por defecto `data/`, o
`LUCIDFENCE_DATA_DIR`): tenants, estados de dispositivos, incidentes,
auditoría hash-chained, credenciales cifradas y cooldowns. El código es
reemplazable; el data dir no.

```bash
# backup consistente (el server puede seguir corriendo; los stores son JSON atómicos)
tar -czf lucidfence-backup-$(date +%F).tar.gz -C "$LUCIDFENCE_DATA_DIR" .
# restore
systemctl stop lucidfence && tar -xzf lucidfence-backup-X.tar.gz -C "$LUCIDFENCE_DATA_DIR" && systemctl start lucidfence
```

Verifica después del restore: `lucidfence doctor` y
`GET /api/audit` → `integrity.ok: true` (la cadena de hashes detecta un
backup corrupto o manipulado).

## Upgrade

```bash
brew upgrade lucidfence        # macOS
# tarball/git: sustituye el código y conserva el data dir
```

- Los datos son compatibles hacia delante dentro de una misma major.
- `lucidfence --version` debe coincidir con la release instalada (hay un
  guardarraíl de versiones en CI que lo garantiza en origen).
- Tras cada upgrade: `lucidfence doctor` + un vistazo a `/api/status`.

## Cadencia de polling vs rate limits

`interval_seconds` (por defecto 900 = 15 min) controla el ciclo del engine.
Cada ciclo hace ~1 request de listado paginado al UEM + lo que disparen las
acciones. Referencias para elegirlo:

| Flota | Intervalo recomendado | Racional |
|---|---|---|
| < 500 dispositivos | 300–900 s | Cualquier UEM lo absorbe sin despeinarse |
| 500–5.000 | 900 s | El check-in MDM típico es ≥15 min: pedir más a menudo no da datos nuevos |
| > 5.000 | 900–1800 s | Paginación larga; vigila los 429 de Graph/Jamf |

Reglas prácticas: no bajes el intervalo por debajo de la cadencia real de
check-in de tu MDM (ver [matriz de ubicación](../integrations/LOCATION_MATRIX.md));
si ves `429`/`transport_error` en el action log, duplica el intervalo antes
de tocar nada más. El benchmark de 10k dispositivos del repo
(`scripts/benchmark_10k.py`) corre el pipeline completo en local si quieres
medir tu hardware.

## Monitorización

- **Salud**: `GET /api/health` (sin auth, loopback) — engánchalo a tu
  Nagios/Uptime-Kuma/cron.
- **Estado profundo**: `GET /api/status` — ciclo, flota, `enforcement`,
  incidentes; `lucidfence status` en CLI.
- **Alertas de incidentes**: webhooks firmados/ntfy hacia donde ya miras —
  recetas en [ALERT_RECIPES.md](ALERT_RECIPES.md).
- **Logs**: launchd/systemd/Docker según despliegue (arriba).

## Checklist de producción

- [ ] Servicio arranca con el sistema (`brew services` / systemd enabled)
- [ ] Credenciales UEM en env file con permisos 600, no en YAML
- [ ] Backup del data dir programado y **restaurado una vez** (probado)
- [ ] `enforcement.mode` deliberado (runbook: [ENFORCEMENT.md](ENFORCEMENT.md))
- [ ] `/api/health` monitorizado
- [ ] Webhook de incidentes apuntando a un canal que alguien lee
