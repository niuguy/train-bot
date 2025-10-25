#!/usr/bin/env bash
set -euo pipefail

# Run the Cloudflare Worker locally with the required bindings.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .dev.vars ]]; then
  # shellcheck disable=SC1091
  set -a
  source .dev.vars
  set +a
fi

missing=0
for var in TELEGRAM_BOT_TOKEN RTT_USERNAME RTT_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "Missing $var. Set it in the environment or in worker/.dev.vars" >&2
    missing=1
  fi
done

if [[ $missing -eq 1 ]]; then
  exit 1
fi

cmd=(yarn dev)
remote=0
local_flags=()
for arg in "$@"; do
  case "$arg" in
    --remote)
      remote=1
      ;;
    *)
      local_flags+=("$arg")
      ;;
  esac
done

if [[ $remote -eq 0 ]]; then
  cmd+=(--local)
else
  cmd+=(--remote)
fi

if [[ ${#local_flags[@]} -gt 0 ]]; then
  cmd+=("${local_flags[@]}")
fi

cmd+=(--)
cmd+=(--var "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}")
cmd+=(--var "RTT_USERNAME=${RTT_USERNAME}")
cmd+=(--var "RTT_PASSWORD=${RTT_PASSWORD}")

if [[ -n "${TRANSPORT_API_APP_ID:-}" && -n "${TRANSPORT_API_APP_KEY:-}" ]]; then
  cmd+=(--var "TRANSPORT_API_APP_ID=${TRANSPORT_API_APP_ID}")
  cmd+=(--var "TRANSPORT_API_APP_KEY=${TRANSPORT_API_APP_KEY}")
fi

exec "${cmd[@]}"
