# Contribuir

1. `make verify` debe estar en verde antes de abrir la PR. Es el mismo gate que
   corre la CI (`.github/workflows/ci.yml`).
2. Lee `ARCHITECTURE.md`: las fronteras entre paquetes y los límites de tamaño
   los valida la CI. Un paquete nuevo se documenta en la tabla de paquetes en el
   mismo commit.
3. Todo claim de producto nuevo añade un check a `internal/battery`. Todo cambio
   de API actualiza `docs/openapi.yaml`.
4. Dependencias nuevas: solo con entrada en `internal/arch/allowlist_*.txt` y
   aprobación del propietario (CODEOWNERS).
5. Agentes: rama `agent/<tema>`, PR automática, automerge si CI verde, ≤ 400
   líneas y sin tocar ficheros CODEOWNERS. Todo lo demás lleva `needs-human`.
6. Commits: Conventional Commits en español (`feat(engine): ...`).
