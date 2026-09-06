#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly ACTION="${1:-config}"
readonly CONTRACTLENS_PLATFORM="${CONTRACTLENS_PLATFORM:-cuda}"

case "${CONTRACTLENS_PLATFORM}" in
    cuda)
        readonly COMPOSE_FILE="${PROJECT_ROOT}/compose.yaml"
        readonly DEFAULT_ENV_FILE="${PROJECT_ROOT}/.env"
        ;;
    ascend)
        readonly COMPOSE_FILE="${PROJECT_ROOT}/compose.ascend.yaml"
        readonly DEFAULT_ENV_FILE="${PROJECT_ROOT}/.env.ascend"
        ;;
    *)
        echo "CONTRACTLENS_PLATFORM must be cuda or ascend; received: ${CONTRACTLENS_PLATFORM}" >&2
        exit 2
        ;;
esac

readonly CONTRACTLENS_ENV_FILE="${CONTRACTLENS_ENV_FILE:-${DEFAULT_ENV_FILE}}"
COMPOSE_ENV_ARGS=()
if [[ -f "${CONTRACTLENS_ENV_FILE}" ]]; then
    COMPOSE_ENV_ARGS=(--env-file "${CONTRACTLENS_ENV_FILE}")
fi

compose() {
    docker compose "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" "$@"
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
        compose down
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
        echo "Usage: CONTRACTLENS_PLATFORM={cuda|ascend} $0 {config|build|up|down|restart|logs|ps}" >&2
        exit 2
        ;;
esac
