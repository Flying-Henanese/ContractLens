#!/usr/bin/env bash
set -Eeuo pipefail

TEMPLATE_CONFIG="${VLM_CONFIG_TEMPLATE:-/opt/paddleocr-server/vllm_config.yaml}"
RUNTIME_CONFIG="${VLM_RUNTIME_CONFIG:-/tmp/vllm_config.yaml}"
MODEL_NAME="${VLM_MODEL:-PaddleOCR-VL-1.6-0.9B}"
DP_SIZE="${VLM_DATA_PARALLEL_SIZE:-2}"
DP_BACKEND="${VLM_DATA_PARALLEL_BACKEND:-mp}"
GPU_MEMORY_UTILIZATION="${VLM_GPU_MEMORY_UTILIZATION:-0.8}"
MAX_NUM_SEQS="${VLM_MAX_NUM_SEQS:-16}"
MAX_NUM_BATCHED_TOKENS="${VLM_MAX_NUM_BATCHED_TOKENS:-16384}"
VISIBLE_DEVICES="${ASCEND_RT_VISIBLE_DEVICES:-}"

is_positive_integer() {
    [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

if [[ ! -f "${TEMPLATE_CONFIG}" ]]; then
    echo "错误：找不到 vLLM 配置模板：${TEMPLATE_CONFIG}" >&2
    exit 1
fi

if ! is_positive_integer "${DP_SIZE}"; then
    echo "错误：VLM_DATA_PARALLEL_SIZE 必须是正整数，当前值：${DP_SIZE}" >&2
    exit 1
fi

if [[ "${DP_BACKEND}" != "mp" && "${DP_BACKEND}" != "ray" ]]; then
    echo "错误：VLM_DATA_PARALLEL_BACKEND 只能是 mp 或 ray，当前值：${DP_BACKEND}" >&2
    exit 1
fi

if [[ -z "${VISIBLE_DEVICES}" ]]; then
    echo "错误：必须设置 ASCEND_RT_VISIBLE_DEVICES，例如 1,2。" >&2
    exit 1
fi

IFS=',' read -r -a visible_npus <<< "${VISIBLE_DEVICES}"
if (( ${#visible_npus[@]} != DP_SIZE )); then
    echo "错误：VLM NPU 数量（${#visible_npus[@]}）必须等于 data-parallel-size（${DP_SIZE}）。" >&2
    echo "ASCEND_RT_VISIBLE_DEVICES=${VISIBLE_DEVICES}" >&2
    exit 1
fi

sed \
    -e "s/^data-parallel-size:.*/data-parallel-size: ${DP_SIZE}/" \
    -e "s/^data-parallel-backend:.*/data-parallel-backend: ${DP_BACKEND}/" \
    -e "s/^gpu-memory-utilization:.*/gpu-memory-utilization: ${GPU_MEMORY_UTILIZATION}/" \
    -e "s/^max-num-seqs:.*/max-num-seqs: ${MAX_NUM_SEQS}/" \
    -e "s/^max-num-batched-tokens:.*/max-num-batched-tokens: ${MAX_NUM_BATCHED_TOKENS}/" \
    "${TEMPLATE_CONFIG}" > "${RUNTIME_CONFIG}"

echo "启动 PaddleOCR-VL 昇腾 VLM Data Parallel 服务"
echo "模型：${MODEL_NAME}"
echo "可见 NPU：${ASCEND_RT_VISIBLE_DEVICES}"
echo "数据并行副本：${DP_SIZE}"
echo "数据并行后端：${DP_BACKEND}"
echo "运行时配置：${RUNTIME_CONFIG}"

exec paddleocr genai_server \
    --model_name "${MODEL_NAME}" \
    --backend vllm \
    --backend_config "${RUNTIME_CONFIG}" \
    --host 0.0.0.0 \
    --port 8118
