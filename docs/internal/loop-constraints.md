# Loop constraints

Structured constraints for the LucidFence improvement loop. Enforced by the
maintainer and the PR verifier (see `docs/internal/LOOP.md`).

## Denylist absoluta (ni con gate QA verde entran nunca)

- Cualquier commit/PR que añada secretos a `config.json`, `data/` o `.env`.
- Publicar `data/cloud_state.json` con datos reales de tenant (es demo-only).
- Wallets de cripto, instrucciones de payout, o cambios ajenos al producto
  geofencing / UEM.
- Modificar el contrato `MDMAdapter` (`base.py`) SIN bump mayor ni preservar
  el mock offline (con bump y mock, sí auto-mergea — ver Push/merge).

## Push / merge rules (auto-merge total en verde — propietario 2026-08-16)

- `main` is protected: no force-push. La revisión humana deja de ser
  requisito de merge; el **gate QA de máquina** la sustituye y es
  innegociable — "auto-merge" significa "sin humano", NUNCA "sin comprobar".
- **Auto-merge de CUALQUIER cambio a `main`** (código de producto incluido:
  auth, `notifier.py`, contrato de adapters, deps MAJOR, postura de
  seguridad) EN CUANTO pase el gate QA completo: CI verde + batería runtime
  N/N + tests de regresión relevantes + `VEREDICTO QA: APTO`. Un cambio de
  seguridad exige además su test de regresión (falla antes / pasa después).
- El contrato `MDMAdapter` (`base.py`) sigue siendo estable: cambiarlo obliga
  a bump mayor y a preservar el mock offline; pero si el PR lo hace bien y
  pasa el gate, auto-mergea (ya no espera a un humano).
- Adapter contributions from the community MUST preserve the offline mock path
  and ship tests that run without real credentials.

## El ÚNICO gate humano: publicar hacia fuera

Lo que sale del repo hacia usuarios/terceros reales NO se automatiza; lo
aprueba el propietario. Todo lo demás (merges a `main`) es auto-merge.

- **Releases a producción**: el commit que toca `.release-version` (dispara
  `release.yml` → Homebrew/descargas). El loop lo deja listo; el propietario
  lo mergea.
- **Outreach a terceros**: las PR `outreach:` de Growth (publican con la
  identidad del propietario). El merge del propietario sigue siendo el "sí".

## Denylist absoluta (ni con gate verde)

Estas nunca entran, las pase quien las pase: secretos en `config.json` /
`data/` / `.env`; publicar `data/cloud_state.json` con datos reales de
tenant; wallets/payout/spam ajeno al producto.
