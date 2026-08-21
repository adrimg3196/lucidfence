# Lanzamiento — publica releases nuevas de forma autónoma (semanal)

El propietario (2026-08-16) pidió que la flota **publique releases nuevas
sola**. Este loop es el dueño del proceso de release de punta a punta: decide
si toca lanzar, bumpea la versión de forma coherente, dispara la publicación
y deja Homebrew apuntando a la versión nueva. La red es el gate de máquina,
no un humano.

## Cuándo lanza (y cuándo NO)

- **Cadencia:** semanal (domingo), después del ciclo de producto del sábado.
- **Sale una release SOLO si hay cambios de cara al usuario en `main` desde
  la última tag** (features/fixes que un admin notaría: código de producto,
  fixes, docs de onboarding relevantes). Si desde la última release solo hubo
  cambios internos (docs de loops, run-log, métricas), NO lanza — nada de
  releases vacías. Un domingo sin novedad reportable es un no-op de una línea.

## Runbook (una release)

1. **¿Toca?** Compara `git log <última-tag>..origin/main`. Si no hay cambios
   de usuario, termina ("sin cambios que publicar"). Si los hay, sigue.
2. **Versión semver** desde la naturaleza de los cambios y el CHANGELOG:
   features → minor; solo fixes → patch. (Major nunca autónomo: romper el
   contrato de adapters o la API es decisión del propietario → deja nota y
   para.)
3. **Bump coherente** en un worktree fresco desde `origin/main`, los CUATRO a
   la vez (los guarda `tests/test_version_consistency.py`): `lucidfence/cli.py`
   (`VERSION`), `pyproject.toml` (`version`), `.release-version`, y una
   sección nueva `## [x.y.z] - AAAA-MM-DD` en `CHANGELOG.md` con lo nuevo/lo
   corregido reales de la ventana.
4. **Verifica** en el worktree: `python3 tests/run_tests.py` (los ~6 fallos
   de `test_oidc_sso.py` son baseline conocida del contenedor) y
   `python3 scripts/runtime_validation.py` (N/N).
5. **Publica**: push a `claude/release-loop`, PR `release: vX.Y.Z`, y con CI
   verde + mergeable haz squash-merge. El merge de `.release-version` dispara
   `release.yml`, que **construye el tarball, lo instala desde cero, arranca
   el servidor y comprueba que responde ANTES de publicar** (ese smoke es el
   gate de máquina de la publicación) → crea el GitHub Release + asset.
6. **Homebrew**: espera a que el asset exista (`get_release_by_tag vX.Y.Z`),
   coge su `digest` (sha256), y en un PR aparte actualiza `Formula/lucidfence.rb`
   del repo (url/sha256/versión + `test do`) — auto-merge en verde. Para el
   **tap** (`adrimg3196/homebrew-lucidfence`) intenta `add_repo` con push y
   actualízalo igual; si la sesión no tiene push al tap, deja el diff exacto
   del tap en `docs/internal/release/pending-tap.md` y anótalo para el digest
   (es el único paso que puede requerir una mano).
7. **Registro**: línea en `docs/internal/loop-run-log.md` y estado en
   `docs/internal/release/history.md` (append-only).

## Reglas duras

- Nunca una release vacía ni sin CHANGELOG real.
- Nunca un bump MAJOR autónomo (contrato de adapters/API = propietario).
- El smoke de `release.yml` es innegociable: si el artefacto no arranca, no
  se publica (el workflow ya falla solo — no lo puentees).
- Sin tocar datos de tenant, secretos ni la denylist de `loop-constraints.md`.
- Estilo regla 8: el resumen final dice la versión publicada y el enlace
  primero.
