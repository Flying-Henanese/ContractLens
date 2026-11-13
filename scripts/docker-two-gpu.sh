#!/usr/bin/env bash
# Use this entry point for every lifecycle action of the two-GPU deployment.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export CONTRACTLENS_PLATFORM=cuda
export CONTRACTLENS_PIPELINE_MODE=replicas
export CONTRACTLENS_PIPELINE_WORKERS=2
export CONTRACTLENS_GPU_LAYOUT=colocated
export PIPELINE_2_STATE=""
export CONTRACTLENS_ENV_FILE="${CONTRACTLENS_ENV_FILE:-${SCRIPT_DIR}/../.env.two-gpu}"
if [[ ! -f "${CONTRACTLENS_ENV_FILE}" ]]; then
    echo "Copy deploy/two-gpu/env.template to .env.two-gpu and configure GPUs/cache first." >&2
    exit 2
fi
exec bash "${SCRIPT_DIR}/docker.sh" "${1:-config}"
