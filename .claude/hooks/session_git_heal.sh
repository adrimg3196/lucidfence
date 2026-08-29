#!/bin/bash
# Cura al arrancar la sesión el "workspace zombi" que deja la plataforma CCR:
# el contenedor restaura a veces una instantánea de DÍAS atrás (pasó: estado
# del 19-08 resucitado el 25-08, tres veces), con refs remotas rancias y un
# HEAD en commits ya entregados hace tiempo. Consecuencias: el stop-hook de
# git acusa "183 commits sin pushear" en falso y cualquier trabajo arranca
# sobre una base vieja. Este hook vive EN el repo porque el repo es lo único
# que la restauración no puede degradar (se reclona/actualiza desde GitHub);
# los parches en ~/.claude se los traga la misma instantánea.
#
# Un hook de arranque JAMÁS debe romper la sesión ni tocar trabajo real:
# todos los caminos salen 0, y la realineación exige TODAS estas firmas del
# zombi a la vez (trabajo varado de verdad no las cumple):
#   1. árbol limpio y sin untracked
#   2. existe la rama homónima en origin (recién refrescada)
#   3. TODOS los commits solo-locales tienen >48 h (nada reciente en vuelo)
#   4. la punta remota es MÁS NUEVA que el commit local más nuevo — la firma
#      inequívoca del rollback; en trabajo varado real el remoto va DETRÁS.
set -u

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
[ -n "$(git remote 2>/dev/null)" ] || exit 0

# Refrescar refs. Sin red: salir en silencio (no `|| true` tras el fetch para
# seguir como si nada — aquí parar ES el comportamiento correcto del hook).
timeout 25 git fetch origin --quiet 2>/dev/null || exit 0

branch="$(git branch --show-current 2>/dev/null)"
[ -n "$branch" ] || exit 0
git rev-parse -q --verify "origin/$branch" >/dev/null 2>&1 || exit 0

git diff --quiet 2>/dev/null || exit 0
git diff --cached --quiet 2>/dev/null || exit 0
[ -z "$(git ls-files --others --exclude-standard 2>/dev/null)" ] || exit 0

newest_local="$(git log --format='%ct' HEAD --not --remotes 2>/dev/null | sort -rn | head -1)"
[ -n "$newest_local" ] || exit 0   # nada solo-local: no hay zombi que curar

now="$(date +%s)"
[ $((now - newest_local)) -gt 172800 ] || exit 0

remote_tip="$(git log -1 --format='%ct' "origin/$branch" 2>/dev/null)"
[ -n "$remote_tip" ] && [ "$remote_tip" -gt "$newest_local" ] || exit 0

git checkout -q -B "$branch" "origin/$branch" 2>/dev/null || exit 0
echo "{\"systemMessage\": \"session_git_heal: workspace zombi realineado a origin/$branch (la instantánea del contenedor había restaurado commits ya entregados)\"}"
exit 0
