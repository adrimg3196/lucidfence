#!/usr/bin/env bash
set -u

destination="${1:-data/recon/latest_recon.txt}"
remote="${2:-origin}"
branch="${3:-recon-state}"
snapshot_in_branch="data/recon/latest_recon.txt"
temp_root="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
temp_snapshot="$(mktemp "${temp_root%/}/lucidfence-recon-load.XXXXXX")"
trap 'rm -f "$temp_snapshot"' EXIT

# Main conserva una copia histórica. Borrarla antes del fetch impide presentar
# datos antiguos como evidencia actual si la rama de snapshots no está disponible.
rm -f "$destination"

if git fetch "$remote" "$branch" --depth 1 \
  && git show "FETCH_HEAD:${snapshot_in_branch}" >"$temp_snapshot"; then
  mkdir -p "$(dirname "$destination")"
  mv "$temp_snapshot" "$destination"
  echo "Snapshot de recon cargado desde ${branch}"
else
  rm -f "$destination" "$temp_snapshot"
  echo "::warning::Snapshot de recon no disponible en ${branch}" >&2
fi
