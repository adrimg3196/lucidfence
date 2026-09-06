# Contribuir

1. `make verify` debe estar en verde antes de abrir la PR. Es el mismo gate que
   corre la CI (`.github/workflows/ci.yml`): `gofmt`/`go vet`/`golangci-lint`,
   `go test -race` con los suelos de cobertura por paquete, y en `web/` —
   `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run gen:api`
   (falla si `git diff --exit-code src/api/schema.d.ts` detecta que el schema
   generado quedó desactualizado) y `npm run build` — además de la batería
   runtime (`internal/battery`) y los e2e de Playwright.
2. Lee `ARCHITECTURE.md`: las fronteras entre paquetes y los límites de tamaño
   los valida la CI. Un paquete nuevo se documenta en la tabla de paquetes en el
   mismo commit.
3. Todo claim de producto nuevo añade un check a `internal/battery`. Todo cambio
   de API actualiza `docs/openapi.yaml`.
4. Dependencias nuevas: solo con entrada en `internal/arch/allowlist_*.txt` y
   aprobación del propietario (CODEOWNERS).
   `tsc` es TypeScript 7 (`@typescript/native`); el paquete `typescript` en
   `package.json` apunta a `@typescript/typescript6` únicamente para que
   `typescript-eslint` cumpla su rango de peer dependency. No "corrijas" esa
   versión.
5. Agentes: rama `agent/<tema>`, PR automática, automerge si CI verde, ≤ 400
   líneas y sin tocar ficheros CODEOWNERS. Todo lo demás lleva `needs-human`.
6. Commits: Conventional Commits en español (`feat(engine): ...`).
