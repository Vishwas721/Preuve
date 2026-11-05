#!/usr/bin/env bash
# Deploy the production stack (Phase 5D): get the images, run migrations, start everything and
# wait until it's healthy.
#
#   infra/scripts/deploy.sh               # pull PREUVE_TAG (default latest) from GHCR
#   infra/scripts/deploy.sh --tag <sha>   # pull a specific CI build
#   infra/scripts/deploy.sh --build       # build the images from this checkout instead
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

BUILD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD=1 ;;
    --tag) export PREUVE_TAG="$2"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$BUILD" = 1 ]; then
  # Local builds are named preuve-api/preuve-web; set the same names in infra/.env.prod so
  # backup/restore scripts use them too.
  export PREUVE_API_IMAGE=preuve-api PREUVE_WEB_IMAGE=preuve-web PREUVE_TAG="${PREUVE_TAG:-local}"
  echo "Building images from $(git -C "$REPO_DIR" rev-parse --short HEAD)…"
  docker build -t "preuve-api:$PREUVE_TAG" "$REPO_DIR/apps/api"
  docker build -t "preuve-web:$PREUVE_TAG" "$REPO_DIR/apps/web"
else
  echo "Pulling images (tag ${PREUVE_TAG:-$(env_value PREUVE_TAG latest)})…"
  compose pull migrate api worker web
fi

echo "Starting the database and running migrations…"
compose up -d postgres redis searxng
compose run --rm migrate
echo "Starting the app…"
compose up -d --remove-orphans
wait_healthy api 180
wait_healthy web 180

PORT="$(env_value WEB_PORT 3100)"
echo "Preuve is up: http://localhost:${PORT}  (health: $(curl -fsS "http://localhost:${PORT}/api/health" || echo 'unreachable'))"
