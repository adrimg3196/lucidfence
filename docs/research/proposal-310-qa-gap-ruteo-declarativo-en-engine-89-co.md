# Investigación: QA: gap ruteo declarativo en engine (#89) + control HMAC saas_api_op sin commitear + toolchain local roto

**Issue:** #310

## QA diario — Test/QA Bot (2026-08-26)

Ejecuté la suite honesta `tests/run_tests.py` con el entorno correcto
(`uv run python`, Py3.11 + requests + playwright). Resultado: **591 passed / 3 failed**.
Los 3 fallos son REALES (no ambientales) y están en `tests/test_89_declarative_routing.py`
(archivo NO commiteado).

### 🔴 Alto — gap de implementación (#89)
1. **Ruteo declarativo en el `engine` NO implementado.**
   `Engine.run_command` (`lucidfence/core/engine.py:699`) no consulta
   `supports_dd

---

*developer_agent el 2026-09-01*
