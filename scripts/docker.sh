#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly ACTION="${1:-config}"

COMPOSE_ARGS=(-f compose.yaml)
if [[ -n "${CONTRACTLENS_ENV_FILE:-}" ]]; then
    COMPOSE_ARGS+=(--env-file "${CONTRACTLENS_ENV_FILE}")
fi

compose() {
    docker compose "${COMPOSE_ARGS[@]}" "$@"
}

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker CLI was not found." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is not available." >&2
    exit 1
fi

cd "${PROJECT_ROOT}"

case "${ACTION}" in
    config)
        compose config --quiet
        ;;
    build)
        compose build --pull
        ;;
    up)
        compose up --detach --remove-orphans
        ;;
    down)
        compose down --remove-orphans
        ;;
    restart)
        compose restart
        ;;
    logs)
        compose logs --follow --tail 200
        ;;
    ps)
        compose ps
        ;;
    *)
        echo "Usage: $0 {config|build|up|down|restart|logs|ps}" >&2
        exit 2
        ;;
esac
