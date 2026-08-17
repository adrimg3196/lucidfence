# Conector GitHub MCP (para que las sesiones cron entreguen PRs)

## El problema que resuelve

La flota de loops (`docs/internal/LOOP.md`) auto-mergea vía las tools
`mcp__github__*` (abrir PR, `get_check_runs`, `merge_pull_request`). Las
sesiones **interactivas** las reciben de la plataforma, pero las sesiones
**frescas que disparan las Routines por cron NO las heredaban** — podían hacer
`git push` pero no abrir ni mergear una PR, así que su trabajo quedaba colgado.
Confirmado en la pasada del 2026-08-16: Admin-value, Roadmap y Growth corrieron
y no entregaron nada (0 PRs).

## El fix: declarar el conector en el repo

`.mcp.json` (raíz del repo) declara el **GitHub MCP server oficial**
([github/github-mcp-server](https://github.com/github/github-mcp-server),
endpoint remoto `https://api.githubcopilot.com/mcp/`). Claude Code carga
`.mcp.json` en **toda** sesión que clone el repo — incluidas las cron. Así el
conector es reproducible y versionado, no dependiente de la plataforma.

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}" }
    }
  }
}
```

## Lo que debe hacer el propietario (una vez)

El token **nunca** se commitea (lo bloquearía gitleaks y es denylist). El
`.mcp.json` lo lee de la variable de entorno `GITHUB_PERSONAL_ACCESS_TOKEN`, que
se configura en los **ajustes del environment de claude.ai** (no en el repo):

1. Crea un **fine-grained PAT** de GitHub con acceso a `adrimg3196/lucidfence`
   y permisos: Contents (RW), Pull requests (RW), Actions (Read), Commit
   statuses (Read).
2. En claude.ai → el environment de la flota → variables de entorno, añade
   `GITHUB_PERSONAL_ACCESS_TOKEN` con ese valor.
3. **Recrea las Routines desde la UI de claude.ai → Routines** (o dispáralas de
   nuevo): las sesiones frescas ya heredarán el conector.

## Verificación

Tras poner el token, dispara una Routine (p. ej. Roadmap) a mano y comprueba que
**abre y mergea su PR**. Si lo hace, replica en las demás. El watchdog del
Guardián sigue anotando como INCIDENTE cualquier loop que corra sin entregar.

## Notas

- En sesiones **interactivas** el `github` ya lo provee la plataforma; este
  `.mcp.json` es sobre todo para las **cron**. Si hubiera cualquier roce, es
  reversible borrando `.mcp.json`.
- Alternativa local (sin depender del remoto): el mismo server por Docker
  (`ghcr.io/github/github-mcp-server`, `GITHUB_PERSONAL_ACCESS_TOKEN` en `-e`),
  si el environment tuviera Docker disponible.

## Plan B activo: el raíl de entrega por Actions (no necesita el environment)

El proxy de las sesiones bloquea llamadas API con tokens propios ("GitHub
access is not enabled for this session"), así que el `.mcp.json` solo funciona
si el environment provee el token. Mientras tanto hay un **raíl de entrega que
vive en el propio GitHub** y no depende del environment:

- **`.github/workflows/agent-pr.yml`** — en cada `git push` a una rama
  `claude/**` (lo único que las sesiones cron SÍ pueden hacer), abre la PR
  contra `main` si no existe.
- **`.github/workflows/agent-automerge.yml`** — cuando la CI de esa PR
  termina en verde, la squash-mergea aplicando el contrato (ramas `claude/**`
  del propio repo; jamás `outreach:`, drafts ni forks; todos los checks del
  gate en verde — solo se ignora el helper `train`).

Ambos usan el **Actions Secret `AGENTS_GITHUB_PAT`** (cifrado; jamás en el
repo). Sin el secret, no-op con aviso en el log.

### Añadir el secret — funciona DESDE EL MÓVIL

1. En el navegador del móvil: `github.com/adrimg3196/lucidfence/settings/secrets/actions`
2. **New repository secret** → Name: `AGENTS_GITHUB_PAT` → Secret: (el PAT
   fine-grained con Contents RW + Pull requests RW) → **Add secret**.
3. Listo: el siguiente push de cualquier loop abre y mergea su PR solo.

Rota el PAT si viajó por un canal inseguro (p. ej. pegado en un chat) y
actualiza el secret con el nuevo valor.
