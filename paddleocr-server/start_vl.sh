#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# 可通过环境变量覆盖，默认使用 1 张 Pipeline GPU + 2 张 VLM GPU。
PIPELINE_GPU_ID="${PIPELINE_GPU_ID:-4}"
VLM_GPU_IDS="${VLM_GPU_IDS:-5,6}"
VLM_DATA_PARALLEL_SIZE="${VLM_DATA_PARALLEL_SIZE:-2}"
VLM_DATA_PARALLEL_BACKEND="${VLM_DATA_PARALLEL_BACKEND:-mp}"
VLM_GPU_MEMORY_UTILIZATION="${VLM_GPU_MEMORY_UTILIZATION:-0.8}"
VLM_MAX_NUM_SEQS="${VLM_MAX_NUM_SEQS:-16}"
VLM_MAX_NUM_BATCHED_TOKENS="${VLM_MAX_NUM_BATCHED_TOKENS:-16384}"

VLM_HOST="${VLM_HOST:-0.0.0.0}"
VLM_PORT="${VLM_PORT:-8118}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8880}"
VLM_MODEL="${VLM_MODEL:-PaddleOCR-VL-1.6-0.9B}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-900}"

VLLM_CONFIG_TEMPLATE="${VLLM_CONFIG_TEMPLATE:-${SCRIPT_DIR}/vllm_config.yaml}"
PIPELINE_CONFIG_TEMPLATE="${PIPELINE_CONFIG_TEMPLATE:-${SCRIPT_DIR}/PaddleOCR-VL-1.6.yaml}"
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/logs}"
RUNTIME_VLLM_CONFIG="${LOG_DIR}/vllm_config.runtime.yaml"
RUNTIME_PIPELINE_CONFIG="${LOG_DIR}/PaddleOCR-VL-1.6.runtime.yaml"
VLM_LOG="${LOG_DIR}/paddleocr-vlm.log"
API_LOG="${LOG_DIR}/paddleocr-vl-api.log"

VLM_PID=""
API_PID=""

mkdir -p "${LOG_DIR}"

is_positive_integer() {
    [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

if [[ ! -f "${VLLM_CONFIG_TEMPLATE}" ]]; then
    echo "错误：找不到 vLLM 配置模板：${VLLM_CONFIG_TEMPLATE}" >&2
    exit 1
fi

if [[ ! -f "${PIPELINE_CONFIG_TEMPLATE}" ]]; then
    echo "错误：找不到 PaddleOCR-VL Pipeline 配置：${PIPELINE_CONFIG_TEMPLATE}" >&2
    exit 1
fi

if ! is_positive_integer "${VLM_DATA_PARALLEL_SIZE}"; then
    echo "错误：VLM_DATA_PARALLEL_SIZE 必须是正整数。" >&2
    exit 1
fi

if [[ "${VLM_DATA_PARALLEL_BACKEND}" != "mp" && "${VLM_DATA_PARALLEL_BACKEND}" != "ray" ]]; then
    echo "错误：VLM_DATA_PARALLEL_BACKEND 只能是 mp 或 ray。" >&2
    exit 1
fi

if [[ "${VLM_GPU_IDS}" =~ [[:space:]] ]]; then
    echo "错误：VLM_GPU_IDS 不能包含空格，请使用逗号分隔，例如 5,6。" >&2
    exit 1
fi

IFS=',' read -r -a VLM_GPU_LIST <<< "${VLM_GPU_IDS}"
if (( ${#VLM_GPU_LIST[@]} != VLM_DATA_PARALLEL_SIZE )); then
    echo "错误：VLM_GPU_IDS 中的 GPU 数量（${#VLM_GPU_LIST[@]}）必须等于 VLM_DATA_PARALLEL_SIZE（${VLM_DATA_PARALLEL_SIZE}）。" >&2
    exit 1
fi

for gpu_id in "${VLM_GPU_LIST[@]}"; do
    if [[ "${gpu_id}" == "${PIPELINE_GPU_ID}" ]]; then
        echo "错误：Pipeline GPU ${PIPELINE_GPU_ID} 不能同时用于 VLM 数据并行副本。" >&2
        exit 1
    fi
done

# 根据环境变量生成临时配置，不修改版本库中的模板。
sed \
    -e "s/^data-parallel-size:.*/data-parallel-size: ${VLM_DATA_PARALLEL_SIZE}/" \
    -e "s/^data-parallel-backend:.*/data-parallel-backend: ${VLM_DATA_PARALLEL_BACKEND}/" \
    -e "s/^gpu-memory-utilization:.*/gpu-memory-utilization: ${VLM_GPU_MEMORY_UTILIZATION}/" \
    -e "s/^max-num-seqs:.*/max-num-seqs: ${VLM_MAX_NUM_SEQS}/" \
    -e "s/^max-num-batched-tokens:.*/max-num-batched-tokens: ${VLM_MAX_NUM_BATCHED_TOKENS}/" \
    "${VLLM_CONFIG_TEMPLATE}" > "${RUNTIME_VLLM_CONFIG}"

sed \
    -e "s|^      server_url:.*|      server_url: http://127.0.0.1:${VLM_PORT}/v1|" \
    "${PIPELINE_CONFIG_TEMPLATE}" > "${RUNTIME_PIPELINE_CONFIG}"

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM

    echo
    echo "正在关闭 PaddleOCR-VL 服务……"

    if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
        kill "${API_PID}" 2>/dev/null || true
        wait "${API_PID}" 2>/dev/null || true
    fi

    if [[ -n "${VLM_PID}" ]] && kill -0 "${VLM_PID}" 2>/dev/null; then
        kill "${VLM_PID}" 2>/dev/null || true
        wait "${VLM_PID}" 2>/dev/null || true
    fi

    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

wait_for_service() {
    local name="$1"
    local pid="$2"
    local url="$3"
    local log_file="$4"
    local start_time
    local elapsed
    start_time=$(date +%s)

    while true; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            echo
            echo "错误：${name} 启动失败。" >&2
            tail -n 100 "${log_file}" || true
            exit 1
        fi

        if curl --silent --fail --max-time 5 "${url}" >/dev/null 2>&1; then
            echo
            echo "${name} 已就绪。"
            return
        fi

        elapsed=$(( $(date +%s) - start_time ))
        if (( elapsed >= STARTUP_TIMEOUT )); then
            echo
            echo "错误：等待 ${name} 启动超时。" >&2
            tail -n 100 "${log_file}" || true
            exit 1
        fi

        printf "\r等待 %s：%d 秒……" "${name}" "${elapsed}"
        sleep 2
    done
}

echo "正在启动 VLM Data Parallel 服务……"
echo "物理 GPU：${VLM_GPU_IDS}"
echo "模型副本：${VLM_DATA_PARALLEL_SIZE}"
echo "并行后端：${VLM_DATA_PARALLEL_BACKEND}"

CUDA_VISIBLE_DEVICES="${VLM_GPU_IDS}" \
uv run --no-sync paddleocr genai_server \
    --model_name "${VLM_MODEL}" \
    --backend vllm \
    --backend_config "${RUNTIME_VLLM_CONFIG}" \
    --host "${VLM_HOST}" \
    --port "${VLM_PORT}" \
    >"${VLM_LOG}" 2>&1 &
VLM_PID=$!

wait_for_service \
    "VLM Data Parallel 服务" \
    "${VLM_PID}" \
    "http://127.0.0.1:${VLM_PORT}/v1/models" \
    "${VLM_LOG}"

echo
echo "正在启动 PaddleOCR-VL Pipeline……"
echo "PP-DocLayoutV3 物理 GPU：${PIPELINE_GPU_ID}"

CUDA_VISIBLE_DEVICES="${PIPELINE_GPU_ID}" \
uv run --no-sync paddlex --serve \
    --pipeline "${RUNTIME_PIPELINE_CONFIG}" \
    --device gpu:0 \
    --host "${API_HOST}" \
    --port "${API_PORT}" \
    >"${API_LOG}" 2>&1 &
API_PID=$!

wait_for_service \
    "PaddleOCR-VL API" \
    "${API_PID}" \
    "http://127.0.0.1:${API_PORT}/openapi.json" \
    "${API_LOG}"

echo
echo "=================================================="
echo "PaddleOCR-VL 多 VLM 副本服务启动成功"
echo "PP-DocLayoutV3 GPU：${PIPELINE_GPU_ID}"
echo "VLM GPU：${VLM_GPU_IDS}（${VLM_DATA_PARALLEL_SIZE} 个副本）"
echo "解析接口：http://服务器IP:${API_PORT}/layout-parsing"
echo "API 文档：http://服务器IP:${API_PORT}/docs"
echo "按 Ctrl+C 关闭所有服务"
echo "=================================================="

wait -n "${VLM_PID}" "${API_PID}"
echo "检测到服务进程退出。" >&2
exit 1