# PRODUCTION — Running LucidFence in Production

This document covers tested limits, data model, backup, crash recovery, and idempotency for production deployments of LucidFence.

## Prerequisites

- Python 3.11+ (use the project `.venv` — see `contributing/DEVELOPMENT.md`)
- A private data directory (not world-readable)
- An OIDC provider for admin authentication (recommended; see `operations/TEAM_ACCESS.md`)
- UEM adapter credentials stored securely (never in repo)

## Installation

```bash
# Clone and install
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
.venv/bin/python -m pip install -e .

# Create data directory
mkdir -p /var/lib/lucidfence/data
chown -R lucidfence:lucidfence /var/lib/lucidfence
chmod 700 /var/lib/lucidfence

# Bootstrap config
.venv/bin/python lucidfence/cli.py init --data-dir /var/lib/lucidfence
```

## Server startup

```bash
# Development/quick start
.venv/bin/python lucidfence/cli.py start

# Production — specify ports and data dir
LUCIDFENCE_DATA_DIR=/var/lib/lucidfence \
LUCIDFENCE_PORT=8765 \
LUCIDFENCE_LOG_LEVEL=WARNING \
.venv/bin/python lucidfence/cli.py start
```

The server binds to `0.0.0.0:8765` by default. Use a reverse proxy (nginx, Caddy) in front for TLS.

## Data model

### Directory structure

```
/var/lib/lucidfence/
├── data/
│   ├── state.json          # State store (fleet, devices, policies)
│   ├── audit.json          # Audit log (append-only)
│   ├── credentials/        # Per-tenant UEM credentials (encrypted)
│   └── sessions/           # Active session tokens
├── logs/
│   ├── server.log          # Application logs
│   └── access.log          # HTTP access log
└── config/
    └── lucidfence.yaml     # Main configuration
```

### State store format

The state store (`data/state.json`) is a JSON file with this top-level structure:

```json
{
  "fleet": {
    "last_sync": "2026-01-15T10:30:00Z",
    "device_count": 150,
    "compliant_count": 142
  },
  "devices": {
    "canonical_id_1": { ... normalized device ... },
    "canonical_id_2": { ... }
  },
  "policies": [
    { "name": "office-geofence", "type": "geofence", ... }
  ],
  "risk_scores": {
    "canonical_id_1": 45,
    "canonical_id_2": 12
  }
}
```

## Backup

### Cron-based backup

Add to crontab (`crontab -e`):

```bash
# Daily backup of state + logs at 03:00
0 3 * * * rsync -a --delete /var/lib/lucidfence/ /backup/lucidfence/$(date +\%Y-\%m-\%d)/

# Weekly retention — keep 30 days
0 4 * * 0 find /backup/lucidfence/ -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

### Manual snapshot

```bash
# Create a point-in-time snapshot
tar czf lucidfence-backup-$(date +%Y%m%d).tar.gz \
  /var/lib/lucidfence/data/ \
  /var/lib/lucidfence/config/
```

### Restore

```bash
# Stop server
.venv/bin/python lucidfence/cli.py stop

# Restore
tar xzf lucidfence-backup-20260115.tar.gz -C /var/lib/lucidfence/

# Start server
.venv/bin/python lucidfence/cli.py start
```

## Crash recovery

LucidFence is designed to recover from crashes gracefully:

1. **State store** — writes are atomic (write to temp, rename). If the process crashes mid-write, the previous valid state is preserved.
2. **Audit log** — append-only; each entry is a JSON line. Crashes may truncate the last partial line, which is ignored on next read.
3. **Session tokens** — stored with expiry; on restart, expired tokens are cleaned automatically.
4. **Adapters** — each adapter's state is independent. A crash in one adapter does not affect others.

### Recovery procedure

```bash
# 1. Check logs for panic/crash indicators
grep -i "panic\|fatal\|exception" /var/lib/lucidfence/logs/server.log

# 2. Validate state store integrity
.venv/bin/python -c "
import json, sys
with open('/var/lib/lucidfence/data/state.json') as f:
    json.load(f)
print('State store OK')
"

# 3. Restart
.venv/bin/python lucidfence/cli.py restart
```

## Idempotency

All mutating operations in LucidFence are idempotent:

| Operation | Idempotency guarantee |
|-----------|----------------------|
| `lucidfence apply policy.yaml` | Re-running with same file produces same state |
| `lucidfence adapter sync` | Re-syncing same device overwrites, no duplicates |
| `lucidfence user create` | Creating same user twice returns existing user |
| `lucidfence server start` | Starting when already running returns error, does not duplicate |

### Why idempotency matters

- Cron jobs and automation can re-run safely
- Network retries don't cause duplicate actions
- Disaster recovery scripts are simpler

## Monitoring

### Health endpoint

```bash
curl http://localhost:8765/api/health
# Returns: {"status": "ok", "version": "1.6.0", "uptime": 3600}
```

### Prometheus metrics (optional)

If compiled with metrics support:

```bash
curl http://localhost:8765/metrics
```

Key metrics to alert on:
- `lucidfence_fleet_compliance_ratio` — below 0.95 = warning
- `lucidfence_sync_duration_seconds` — above 30s = investigation
- `lucidfence_error_rate` — above 1% = critical

### Log monitoring

Watch for these patterns:

```bash
# Compliance gaps appearing
grep "compliance.*false" /var/lib/lucidfence/logs/server.log

# Sync failures
grep "sync.*failed" /var/lib/lucidfence/logs/server.log

# Adapter authentication errors
grep "auth.*error\|401\|403" /var/lib/lucidfence/logs/server.log
```

## Scaling limits (tested)

| Metric | Tested limit | Notes |
|--------|--------------|-------|
| Devices in fleet | 10,000 | Linear memory growth, ~200MB for 10k devices |
| Policy evaluations/sec | 500 | Single-core; horizontal scaling via multiple instances |
| Sync interval | 5 minutes | Below 5min, adapter rate limits may apply |
| Concurrent web clients | 50 | Per server instance; use proxy offload for more |

## Security

### TLS termination

Use a reverse proxy for TLS. Example with Caddy:

```caddy
lucidfence.example.com {
    reverseproxy localhost:8765
    tls your@email.com
}
```

### Credential isolation

UEM credentials are stored per-tenant and encrypted at rest. The encryption key is loaded from environment variable `LUCIDFENCE_ENCRYPTION_KEY` (32 bytes hex) or from a vault.

### Network isolation

- Bind to `127.0.0.1` if only local access needed
- Use firewall rules to restrict access to admin CIDR
- Never expose the admin API without authentication

## Troubleshooting

### Server won't start

```bash
# Check port binding
lsof -i :8765

# Check data dir permissions
ls -la /var/lib/lucidfence/data/

# Run with debug logging
LUCIDFENCE_LOG_LEVEL=DEBUG .venv/bin/python lucidfence/cli.py start
```

### Devices not syncing

```bash
# Check adapter status
.venv/bin/python lucidfence/cli.py adapter status

# Force re-sync
.venv/bin/python lucidfence/cli.py adapter sync --all

# Check adapter logs
tail -f /var/lib/lucidfence/logs/adapter-*.log
```

### High memory usage

```bash
# Check state store size
ls -lh /var/lib/lucidfence/data/state.json

# If > 100MB, consider:
# 1. Archiving old audit entries
.venv/bin/python lucidfence/cli.py audit archive --older 90d
# 2. Pruning stale devices
.venv/bin/python lucidfence/cli.py fleet prune --stale 30d
```

## Log rotation

Add to `/etc/logrotate.d/lucidfence`:

```
/var/lib/lucidfence/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## See also

- [`operations/RUNBOOK.md`](RUNBOOK.md) — Operator playbook
- [`operations/DAY2.md`](DAY2.md) — Day 2 operations
- [`architecture/THREAT_MODEL.md`](THREAT_MODEL.md) — Threat model
- [`contributing/DEVELOPMENT.md`](../contributing/DEVELOPMENT.md) — Development setup
