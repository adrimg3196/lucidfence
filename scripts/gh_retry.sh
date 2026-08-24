#!/usr/bin/env bash
# Bounded retry helper for GitHub CLI calls made by operational workflows.
# Source this file, then call: gh_retry api repos/owner/repo

gh_retry_is_retryable() {
  # `${1,,}` es bash 4+; el bash de sistema en macOS es 3.2 (todas las máquinas
  # de la flota), donde revienta con "bad substitution" y tumbaba los 5 tests de
  # test_cron_watchdog.py → verify.py nunca podía dar verde en local, sólo en el
  # runner Ubuntu de CI. `tr` es POSIX y da el mismo resultado en 3.2 y 5.x.
  local error_text
  error_text="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"

  if [[ "$error_text" =~ \(http[[:space:]]+(429|500|502|503|504)\) ]]; then
    return 0
  fi
  case "$error_text" in
    *"api rate limit exceeded"*|*"secondary rate limit"*|\
      *"connection reset"*|*"connection refused"*|\
      *"connection timed out"*|*"temporary failure"*|\
      *"tls handshake timeout"*|*"unexpected eof"*|\
      *"server disconnected"*)
      return 0
      ;;
  esac
  return 1
}


gh_retry() {
  local reconcile_fn=""
  local max_attempts="${GH_RETRY_MAX_ATTEMPTS:-3}"
  local delay="${GH_RETRY_BASE_DELAY:-1}"
  local attempt=1
  local exit_code=1
  local reconcile_code=1
  local error_text=""
  local retry_dir stdout_file stderr_file

  if [[ "${1:-}" == "--reconcile" ]]; then
    reconcile_fn="${2:-}"
    if [[ -z "$reconcile_fn" ]] || ! declare -F "$reconcile_fn" >/dev/null; then
      echo "gh_retry: --reconcile requiere el nombre de una función existente" >&2
      return 2
    fi
    shift 2
  fi
  if (($# == 0)); then
    echo "gh_retry: falta el comando de gh" >&2
    return 2
  fi

  if ! [[ "$max_attempts" =~ ^[1-9][0-9]*$ ]]; then
    echo "gh_retry: GH_RETRY_MAX_ATTEMPTS debe ser un entero positivo" >&2
    return 2
  fi
  if ! [[ "$delay" =~ ^[0-9]+$ ]]; then
    echo "gh_retry: GH_RETRY_BASE_DELAY debe ser un entero no negativo" >&2
    return 2
  fi

  retry_dir=$(mktemp -d "${TMPDIR:-/tmp}/lucidfence-gh-retry.XXXXXX")
  stdout_file="$retry_dir/stdout"
  stderr_file="$retry_dir/stderr"

  while ((attempt <= max_attempts)); do
    : >"$stdout_file"
    : >"$stderr_file"
    if gh "$@" >"$stdout_file" 2>"$stderr_file"; then
      cat "$stdout_file"
      if [[ -s "$stderr_file" ]]; then
        cat "$stderr_file" >&2
      fi
      rm -f "$stdout_file" "$stderr_file"
      rmdir "$retry_dir"
      return 0
    else
      exit_code=$?
    fi

    error_text=$(<"$stderr_file")
    if ! gh_retry_is_retryable "$error_text"; then
      echo "gh_retry: error no reintentable; se detiene tras el intento $attempt" >&2
      cat "$stderr_file" >&2
      if [[ -s "$stdout_file" ]]; then
        cat "$stdout_file" >&2
      fi
      rm -f "$stdout_file" "$stderr_file"
      rmdir "$retry_dir"
      return "$exit_code"
    fi
    if [[ -n "$reconcile_fn" ]]; then
      if "$reconcile_fn" >/dev/null; then
        echo "gh_retry: efecto ya confirmado tras respuesta transitoria" >&2
        rm -f "$stdout_file" "$stderr_file"
        rmdir "$retry_dir"
        return 0
      else
        reconcile_code=$?
      fi
      if ((reconcile_code > 1)); then
        echo "gh_retry: reconciliación indeterminada; no se reintenta la mutación" >&2
        rm -f "$stdout_file" "$stderr_file"
        rmdir "$retry_dir"
        return "$reconcile_code"
      fi
    fi
    if ((attempt == max_attempts)); then
      echo "gh_retry: agotados $max_attempts intentos; operación bloqueada" >&2
      cat "$stderr_file" >&2
      if [[ -s "$stdout_file" ]]; then
        cat "$stdout_file" >&2
      fi
      rm -f "$stdout_file" "$stderr_file"
      rmdir "$retry_dir"
      return "$exit_code"
    fi

    echo "gh_retry: fallo transitorio en intento $attempt/$max_attempts; reintentando" >&2
    if ((delay > 0)); then
      sleep "$delay"
    fi
    delay=$((delay * 2))
    attempt=$((attempt + 1))
  done
}
