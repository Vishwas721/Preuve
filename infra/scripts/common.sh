# Shared by the production scripts (Phase 5D). Source it; don't run it.
set -euo pipefail
# Git Bash on Windows rewrites "/usr/..." arguments into Windows paths; container paths must
# pass through untouched. (No effect on Linux/macOS.)
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

# Host paths handed to docker must be native; `pwd -W` gives C:/... on Git Bash.
_abs() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }
INFRA_DIR="$(_abs "$(dirname "${BASH_SOURCE[0]}")/..")"
REPO_DIR="$(_abs "$INFRA_DIR/..")"
ENV_FILE="${PREUVE_ENV_FILE:-$INFRA_DIR/.env.prod}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy infra/.env.prod.example and fill in the secrets." >&2
  exit 1
fi

compose() {
  docker compose -p preuve-prod --env-file "$ENV_FILE" -f "$INFRA_DIR/docker-compose.prod.yml" "$@"
}

env_value() {  # env_value NAME DEFAULT
  local v
  v="$(grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
  echo "${v:-$2}"
}

wait_healthy() {  # wait_healthy SERVICE [timeout seconds]
  local svc="$1" limit="${2:-180}" waited=0 state
  while :; do
    state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "$(compose ps -q "$svc")" 2>/dev/null || echo missing)"
    [ "$state" = "healthy" ] && return 0
    if [ "$waited" -ge "$limit" ]; then
      echo "$svc is '$state' after ${limit}s" >&2
      compose logs --tail 40 "$svc" >&2 || true
      return 1
    fi
    sleep 3
    waited=$((waited + 3))
  done
}
