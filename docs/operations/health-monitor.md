# LucidFence Health Monitor — Operations

Path: `scripts/health_monitor.py`
Coverage: local + always-on + optional metrics server

## Basic usage

```bash
python3 scripts/health_monitor.py
```

Exit 0 means healthy. Exit 1 means failure. Output is JSON with:

- `checked_at`
- `host`
- `result` from `/api/health`

## Single shot with structured JSON logs

```bash
python3 scripts/health_monitor.py --json-log
```

Writes one JSON object per line with event `health_check` and fields:

- `ts` wall-clock UTC ISO-8601
- `host`
- `http_status` last observed HTTP status if available
- `status` one of `ok`, `degraded`, `critical`

## Serve Prometheus-like metrics

```bash
python3 scripts/health_monitor.py --serve-metrics --metrics-port 9105
```

Endpoints:

- `GET /metrics`
- `GET /healthz`
- `GET /readyz`

## Failure behavior

On failure:

- finds or creates GitHub issue with labels `infrastructure, WS3-platform-ops, P1, roadmap`
- enriches with `severity` and `canonical_alerts`
- adds a fix playbook for restart

On success:

- closes open matching issue with a ✅ comment including the `/api/health` payload
