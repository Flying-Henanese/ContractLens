#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly ACTION="${1:-config}"
readonly CONTRACTLENS_PLATFORM="${CONTRACTLENS_PLATFORM:-cuda}"

case "${CONTRACTLENS_PLATFORM}" in
    cuda)
        readonly COMPOSE_FILE="${PROJECT_ROOT}/compose.yaml"
        ;;
    ascend)
        readonly COMPOSE_FILE="${PROJECT_ROOT}/compose.ascend.yaml"
        ;;
    *)
        echo "CONTRACTLENS_PLATFORM must be cuda or ascend; received: ${CONTRACTLENS_PLATFORM}" >&2
        exit 2
        ;;
esac

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
        docker compose -f "${COMPOSE_FILE}" config --quiet
        ;;
    build)
        docker compose -f "${COMPOSE_FILE}" build --pull
        ;;
    up)
        docker compose -f "${COMPOSE_FILE}" up --detach --remove-orphans
        ;;
    down)
        docker compose -f "${COMPOSE_FILE}" down
        ;;
    restart)
        docker compose -f "${COMPOSE_FILE}" restart
        ;;
    logs)
        docker compose -f "${COMPOSE_FILE}" logs --follow --tail 200
        ;;
    ps)
        docker compose -f "${COMPOSE_FILE}" ps
        ;;
    *)
        echo "Usage: CONTRACTLENS_PLATFORM={cuda|ascend} $0 {config|build|up|down|restart|logs|ps}" >&2
        exit 2
        ;;
esac
