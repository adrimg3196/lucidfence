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
