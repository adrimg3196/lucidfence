# Sobre común de atestación de dispositivo

`lucidfence/core/device_attestation.py` define el contrato neutral para evidencias de confianza de Apple Managed Device Attestation, Android Enterprise Device Trust y Windows Device Health Attestation.

## Contrato

Cada evidencia normalizada es un `AttestationEnvelope` serializable de forma determinista con:

- `source`: `apple`, `android` o `windows`.
- `subject`: identificador local del dispositivo atestado.
- `claims`: claims canónicos (`hardware_backed`, `managed`, `os_integrity`, `encryption`). Cada claim es `{status, value, reason}`.
- `issued_at`, `observed_at`, `expires_at`: timestamps ISO-8601 UTC. El modelo rechaza timestamps sin zona, `issued_at` posterior a `observed_at` y expiraciones anteriores a la emisión.
- `nonce`: nonce preservado si el fabricante/verificador lo reporta.
- `verifier`: verificador oficial o componente que produjo el estado de firma.
- `signature_status`: `verified`, `unverified`, `invalid` o `unknown`.
- `raw_hash`: SHA-256 hex del payload/veredicto/cadena reportada, nunca el payload bruto.
- `provenance`: nombre del payload de origen, campo usado como hash y claims originales.
- `explanation`: texto legible para auditoría.

## Semántica fail-unknown

La ausencia de un claim queda como:

```json
{"status":"unknown","value":null,"reason":"claim absent in <source> attestation payload"}
```

No se convierte en `false` ni en incumplimiento. Un `false` explícito del fabricante sí se conserva como `asserted` con `value:false`.

## API local de solo lectura

`GET /api/device-attestation` devuelve los sobres persistidos en `DeviceState.attestation` para el tenant autenticado. Requiere `device:read`, no consulta UEMs en vivo, no publica payloads de atestación en `cloud_state` y conserva diferencias de procedencia por evidencia.

## Uso offline mínimo

```python
from lucidfence.core.device_attestation import normalize_attestation

envelope = normalize_attestation("apple", raw_payload, observed_at="2026-09-02T10:01:00Z")
wire = envelope.to_json()  # JSON canónico determinista
```
