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
# Read only numeric GPU selectors; never source an environment file as shell code.
for gpu_key in COLOCATED_GPU_1 COLOCATED_GPU_2; do
    gpu_value="${!gpu_key:-}"
    if [[ -z "${gpu_value}" ]]; then
        gpu_value="$(sed -n "s/^${gpu_key}=//p" "${CONTRACTLENS_ENV_FILE}" | tr -d '\r')"
    fi
    if [[ ! "${gpu_value}" =~ ^[0-9]+$ ]]; then
        echo "${gpu_key} must be a host GPU index from nvidia-smi." >&2
        exit 2
    fi
    export "${gpu_key}=${gpu_value}"
done
if (( 10#${COLOCATED_GPU_1} == 10#${COLOCATED_GPU_2} )); then
    echo "Select two distinct host GPUs." >&2
    exit 2
fi
exec bash "${SCRIPT_DIR}/docker.sh" "${1:-config}"
