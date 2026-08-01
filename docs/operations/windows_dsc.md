# Windows PowerShell Desired State Configuration (DSC) Support Matrix

LucidFence implements **PowerShell Desired State Configuration (DSC)** to enforce compliance states declaratively and idempotently on Windows 10/11 endpoints.

This document describes the design, deployment specifications, and compatibility matrix for the Windows DSC integration.

---

## Design and Benefits

While standard configuration checks on Windows endpoints are traditionally executed imperatively (polling-based), declarative configuration enforcement via DSC delivers major performance advantages:
1. **Reduced Orchestration Overhead**: The desired compliance policy document is generated and published once to the endpoint.
2. **Local Drift Correction**: The Local Configuration Manager (LCM) or the DSC v3 engine locally monitors and continuously re-converges to the desired state without requiring network round-trips to the central server.
3. **Idempotency**: If the device state matches the target policy, applying or verifying the configuration is a no-op, preventing configuration thrashing.

---

## Support Matrix

Para consultar el detalle de compatibilidad de Windows, DSC v3 vs v2, los requisitos de PowerShell, así como el soporte de otras plataformas MDM y adapters en LucidFence, consulte la [Matriz de Soporte Declarativa Unificada](declarative-support-matrix.md).

---

## Adapter Implementation

To use DSC capabilities on Windows endpoints, check the `supports_dsc` attribute and execute the declarative actions.

### 1. Verification of DSC Capabilities
```python
from lucidfence.core.adapters.windows_conformidad import WindowsConformidadAdapter

adapter = WindowsConformidadAdapter()
if getattr(adapter, "supports_dsc", False):
    print("Windows endpoint supports declarative DSC enforcement!")
```

### 2. Declarative Policy Generation (`apply_dsc`)
Pass the geofence Policy dictionary or model inside the `params` with the key `"policy"` to generate native DSC manifests and fallback configurations.

```python
result = adapter.execute(device, "apply_dsc", {"policy": policy})
print(result["dsc_v3"])           # DSC v3 JSON Manifest
print(result["dsc_classic_ps1"])   # DSC v2 PS1 Configuration script
print(result["dsc_classic_mof"])   # Compiled MOF representation
```

### 3. Compliance Readback Parsing
Status outputs generated from the DSC agents can be read back and mapped into the LucidFence Device State model to keep the dashboard up-to-date.

```python
status_output_json = '{"results": [{"name": "LucidFencePolicy_pol-1", "inDesiredState": true}]}'
report = adapter.execute(device, "report", {"dsc_status_output": status_output_json})

print(report["devices"][0]["compliant"])  # True
```
