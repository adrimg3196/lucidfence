#!/usr/bin/env bash
set -euo pipefail

snapshot_path="${1:-data/recon/latest_recon.txt}"
remote="${2:-origin}"
branch="${3:-recon-state}"
snapshot_in_branch="data/recon/latest_recon.txt"
temp_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
temp_snapshot="$(mktemp "${temp_root%/}/lucidfence-recon-publish.XXXXXX")"
trap 'rm -f "$temp_snapshot"' EXIT

if [[ ! -f "$snapshot_path" ]]; then
  echo "ERROR: snapshot de recon no encontrado: $snapshot_path" >&2
  exit 1
fi

cp "$snapshot_path" "$temp_snapshot"

# El checkout del workflow es efímero y el snapshot ya está preservado.
# Descartar la copia trackeada evita que el cambio bloquee el cambio de rama.
git checkout -- .
git fetch "$remote" "$branch" --depth 1 || true
if git show-ref --verify --quiet "refs/remotes/${remote}/${branch}"; then
  git checkout -B "$branch" "${remote}/${branch}"
else
  git checkout --orphan "$branch"
  git rm -rf --cached . >/dev/null 2>&1 || true
fi

mkdir -p "$(dirname "$snapshot_in_branch")"
cp "$temp_snapshot" "$snapshot_in_branch"
git add -f "$snapshot_in_branch"

if git diff --cached --quiet; then
  echo "Sin cambios en el snapshot de recon"
else
  run_ref="${GITHUB_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
  git commit -m "chore(recon): snapshot de recon social (${run_ref})"
  git push "$remote" "HEAD:refs/heads/${branch}"
fi
