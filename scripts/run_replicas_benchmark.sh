#!/usr/bin/env bash
# Controlled CUDA experiment, never a production rollout or automatic retry loop.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
readonly GROUP="${1:?usage: run_replicas_benchmark.sh A|B|C label [pages|all] [repeats]}"
readonly LABEL="${2:?a unique run label is required}"
readonly PAGES="${3:-1,2,3,6,7,8,30,40,80,120,160,200,240,280,320,360}"
readonly REPEATS="${4:-3}"
[[ "${LABEL}" =~ ^[A-Za-z0-9_-]+$ && "${REPEATS}" =~ ^[1-9][0-9]*$ ]]
export CONTRACTLENS_PLATFORM=cuda CONTRACTLENS_PIPELINE_MODE=replicas
export PIPELINE_2_STATE=""
case "${GROUP}" in
    A|C) export PIPELINE_SUBGRAPH_CONCURRENCY=16 ;;
    B) export PIPELINE_SUBGRAPH_CONCURRENCY=8 ;;
    *) echo "group must be A, B or C" >&2; exit 2 ;;
esac
benchmark() {
    docker run --rm --user "$(id -u):$(id -g)" --gpus all --network host \
        -v "${PWD}:/work" -w /work -e PYTHONPATH=/work/src \
        --entrypoint python "${BENCHMARK_CLIENT_IMAGE:-pdf-parser:validation-b82488d}" \
        scripts/benchmark_replicas.py --pdf tmp/pdfs/book.pdf --run "$1" --pages "$2" --concurrency "$3"
}
bash scripts/docker.sh config
bash scripts/docker.sh up
# Warm both workers before selecting the one-worker control.
benchmark "${LABEL}-warm" "1,2,80,160" 2
if [[ "${GROUP}" == A ]]; then
    export PIPELINE_2_STATE=down
    bash scripts/docker.sh up
fi
for ((round=1; round<=REPEATS; round++)); do
    run="${LABEL}-${round}"
    benchmark "${run}" "${PAGES}" 8
    docker inspect contractlens-paddleocr-vlm-server-1 contractlens-pipeline-1-1 \
        contractlens-pipeline-2-1 --format '{{.Name}} {{.State.Status}} {{.RestartCount}}' \
        > "output/smoke/${run}/container-state.txt"
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' \
        contractlens-paddleocr-vlm-server-1 contractlens-pipeline-1-1 contractlens-pipeline-2-1 \
        > "output/smoke/${run}/container-resources.txt"
    docker logs contractlens-paddleocr-vl-api-1 2>/dev/null | \
        rg --fixed-strings "${run}-" > "output/smoke/${run}/proxy.jsonl"
done
