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

cd "${PROJECT_ROOT}"
readonly CONTRACTLENS_ENV_FILE="${CONTRACTLENS_ENV_FILE:-${DEFAULT_ENV_FILE}}"

# Read only literal topology settings. Do not execute the Compose env file as Bash.
topology_setting() {
    local name="$1" fallback="$2" value
    value="${!name-}"
    if [[ -z "${value}" && "${CONTRACTLENS_PLATFORM}" == ascend && -f "${CONTRACTLENS_ENV_FILE}" ]]; then
        value="$(awk -v name="${name}" -v single_quote="'" '
            $0 ~ "^[[:space:]]*(export[[:space:]]+)?" name "[[:space:]]*=" {
                value = $0
                sub(/^[^=]*=[[:blank:]]*/, "", value)
                sub(/[[:space:]]+#.*$/, "", value)
                sub(/[[:space:]]+$/, "", value)
                quote = substr(value, 1, 1)
                if (length(value) > 1 && (quote == "\"" || quote == single_quote) &&
                    substr(value, length(value)) == quote) {
                    value = substr(value, 2, length(value) - 2)
                }
            }
            END { print value }
        ' "${CONTRACTLENS_ENV_FILE}")"
    fi
    printf '%s\n' "${value:-${fallback}}"
}

validate_colocated_ids() {
    local name="$1" value="$2" require_unique="$3"
    local id seen=,
    local -a ids

    if [[ ! "${value}" =~ ^(0|[1-9][0-9]*)(,(0|[1-9][0-9]*)){3}$ ]]; then
        echo "${name} must contain four comma-separated NPU IDs." >&2
        exit 2
    fi
    if [[ "${require_unique}" == true ]]; then
        IFS=, read -r -a ids <<< "${value}"
        for id in "${ids[@]}"; do
            if [[ "${seen}" == *",${id},"* ]]; then
                echo "${name} must contain distinct NPU IDs." >&2
                exit 2
            fi
            seen+="${id},"
        done
    fi
}

configure_colocated_devices() {
    local device_ids pipeline_ids vlm_ids index
    local -a devices pipeline vlm

    device_ids="$(topology_setting CONTRACTLENS_COLOCATED_NPU_IDS 4,5,6,7)"
    pipeline_ids="$(topology_setting CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS "${device_ids}")"
    vlm_ids="$(topology_setting CONTRACTLENS_COLOCATED_VLM_RT_IDS "${device_ids}")"
    validate_colocated_ids CONTRACTLENS_COLOCATED_NPU_IDS "${device_ids}" true
    validate_colocated_ids CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS "${pipeline_ids}" false
    validate_colocated_ids CONTRACTLENS_COLOCATED_VLM_RT_IDS "${vlm_ids}" true
    IFS=, read -r -a devices <<< "${device_ids}"
    IFS=, read -r -a pipeline <<< "${pipeline_ids}"
    IFS=, read -r -a vlm <<< "${vlm_ids}"
    for index in 0 1 2 3; do
        export "CONTRACTLENS_COLOCATED_DEVICE_$((index + 1))=${devices[index]}"
        export "CONTRACTLENS_COLOCATED_WORKER_RT_$((index + 1))=${pipeline[index]}"
    done
    # CANN requires an ascending visibility list. The shared server can assign any rank.
    VLM_NPU_IDS="$(printf '%s\n' "${vlm[@]}" | sort -n | paste -sd , -)"
    export VLM_NPU_IDS
    export VLM_DATA_PARALLEL_SIZE=4
    export VLM_DATA_PARALLEL_BACKEND=mp
}

COMPOSE_OVERLAY_ARGS=()
PIPELINE_MODE="$(topology_setting CONTRACTLENS_PIPELINE_MODE single)"
case "${PIPELINE_MODE}" in
    single) ;;
    replicas|colocated)
        if [[ "${CONTRACTLENS_PLATFORM}" != ascend ]]; then
            echo "Pipeline mode ${PIPELINE_MODE} requires Ascend." >&2
            exit 2
        fi
        COMPOSE_OVERLAY_ARGS=(-f "${PROJECT_ROOT}/compose.replicas.ascend.yaml")
        if [[ "${PIPELINE_MODE}" == colocated ]]; then
            configure_colocated_devices
            COMPOSE_OVERLAY_ARGS+=(
                -f "${PROJECT_ROOT}/compose.replicas4.ascend.yaml"
                -f "${PROJECT_ROOT}/compose.colocated.ascend.yaml"
            )
        else
            case "$(topology_setting CONTRACTLENS_PIPELINE_WORKERS 2)" in
                2) ;;
                4) COMPOSE_OVERLAY_ARGS+=(-f "${PROJECT_ROOT}/compose.replicas4.ascend.yaml") ;;
                *) echo "Pipeline workers must be 2 or 4." >&2; exit 2 ;;
            esac
        fi
        ;;
    *) echo "Pipeline mode must be single, replicas, or colocated." >&2; exit 2 ;;
esac

COMPOSE_ENV_ARGS=()
if [[ -f "${CONTRACTLENS_ENV_FILE}" ]]; then
    COMPOSE_ENV_ARGS=(--env-file "${CONTRACTLENS_ENV_FILE}")
fi

compose() {
    docker compose ${COMPOSE_ENV_ARGS[@]+"${COMPOSE_ENV_ARGS[@]}"} -f "${COMPOSE_FILE}" ${COMPOSE_OVERLAY_ARGS[@]+"${COMPOSE_OVERLAY_ARGS[@]}"} "$@"
}

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker CLI was not found." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is not available." >&2
    exit 1
fi

case "${ACTION}" in
    config)
        if (( $# > 1 )); then
            compose config "${@:2}"
        else
            compose config --quiet
        fi
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
