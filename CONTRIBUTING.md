# Contributing — review process

Quesitos minimos antes de abrir PR o pedir merge:

- `python3 tests/run_tests.py` verde.
- `git diff --stat` acotado al scope del issue/feature.
- No hay secretos, tokens, cookies ni credenciales; `.env.example` con placeholders.
- Si toca frontend: probar `http://127.0.0.1:8765/static/dashboard.html` y `cloud.html` en headless o browser real.
- Si toca seguridad: incluir test o verificación curl de headers/auth.
- Si toca Docker: `docker compose config` y comentar resultado; si docker no aplica, documentar blocker exacto.
- PR description debe indicar: issue resuelto, QA ejecutada, screenshots/smoke test si aplica.

Para reviews:
- Revisor debe confirmar checklist y pedir cambios concretos, no genericos.
- En caso de conflicto: `git checkout --ours` + ajuste manual en el archivo roto, nunca merge ciego.
