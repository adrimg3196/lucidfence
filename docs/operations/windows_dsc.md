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

| OS / Component | PowerShell Version | DSC Version | Enforcement Style | Emitter Formats |
|---|---|---|---|---|
| **Windows 11** | PowerShell 7.2+ | DSC v3 | Native Declarative | JSON Manifest, PS1 |
| **Windows 10** | PowerShell 7.2+ | DSC v3 | Native Declarative | JSON Manifest, PS1 |
| **Windows 10/11** | PowerShell 5.1 | DSC v2 (Legacy) | Local LCM / MOF | PS1 Script, MOF File |

### PowerShell 7 + DSC v3 (Preferred)
In modern Windows deployments running PowerShell 7, **DSC v3** is the preferred engine.
- It uses declarative **JSON / YAML resource manifests** for desired state documents.
- Configuration is processed directly by the DSC v3 engine, aligning with the OpenAPI specs and cloud deployment methods.

### PowerShell 5.1 + DSC v2 (Fallback)
On standard Windows endpoints where only PowerShell 5.1 is present:
- Desired state is generated as classic DSC **PowerShell scripts (`.ps1`)** and compiled into **Managed Object Format (`.mof`)** documents.
- The built-in Local Configuration Manager (LCM) processes the MOF to verify and correct compliance.

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
