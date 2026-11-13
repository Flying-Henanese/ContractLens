#!/usr/bin/env bash
# Independent-page verification for an already healthy colocated deployment.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
LABEL="${1:?usage: benchmark_two_gpu.sh unique-label}"
[[ "${LABEL}" =~ ^[A-Za-z0-9_-]+$ ]]
CLIENT_IMAGE="${BENCHMARK_CLIENT_IMAGE:-pdf-parser:two-gpu}"
bash scripts/docker-two-gpu.sh config
bash scripts/docker-two-gpu.sh ps
for service in api paddleocr-vl-api pipeline-1 pipeline-2 paddleocr-vlm-server; do
    [[ "$(docker inspect "contractlens-${service}-1" --format '{{.State.Health.Status}}')" == healthy ]]
done
benchmark() {
    local run="$1" pages="$2" concurrency="$3" status=0
    shift 3
    docker run --rm --user "$(id -u):$(id -g)" --gpus all --network host \
        -v "${PWD}:/work" -w /work -e PYTHONPATH=/work/src \
        --entrypoint python "${CLIENT_IMAGE}" scripts/benchmark_replicas.py \
        --pdf tmp/pdfs/book.pdf --run "${run}" --pages "${pages}" --concurrency "${concurrency}" "$@" || status=$?
    if [[ -f RELEASE_COMMIT ]]; then
        cat RELEASE_COMMIT > "output/smoke/${run}/revision.txt"
    else
        git rev-parse HEAD > "output/smoke/${run}/revision.txt"
    fi
    docker inspect contractlens-paddleocr-vlm-server-1 contractlens-pipeline-1-1 contractlens-pipeline-2-1 \
        --format '{{.Name}} {{.State.Status}} {{.State.Health.Status}} {{.RestartCount}}' \
        > "output/smoke/${run}/container-state.txt"
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' \
        contractlens-paddleocr-vlm-server-1 contractlens-pipeline-1-1 contractlens-pipeline-2-1 \
        > "output/smoke/${run}/container-resources.txt"
    docker logs contractlens-paddleocr-vl-api-1 2>/dev/null | grep -F "${run}-" \
        > "output/smoke/${run}/proxy.jsonl"
    # All attempted with recorded failures is a diagnostic result, never a pass.
    if (( status != 0 )); then
        if [[ "$*" != *--continue-timeout-pages* || "${status}" != 1 ]]; then
            return "${status}"
        fi
        echo "${run}: completed with failures; inspect summary.json"
        return "${status}"
    fi
}
benchmark "${LABEL}-warm" 1,2,80,160 2
for round in 1 2 3; do
    benchmark "${LABEL}-sample-${round}" 1,2,3,6,7,8,30,40,80,120,160,200,240,280,320,360 8
done
benchmark "${LABEL}-full-1" all 8 --continue-timeout-pages
