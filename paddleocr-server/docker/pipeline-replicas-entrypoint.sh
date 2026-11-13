#!/usr/bin/env bash
set -Eeuo pipefail
readonly LIMIT="${PIPELINE_SUBGRAPH_CONCURRENCY:-16}"
if [[ ! "${LIMIT}" =~ ^[1-9][0-9]*$ ]]; then
    echo "PIPELINE_SUBGRAPH_CONCURRENCY must be a positive integer" >&2
    exit 2
fi
sed "s/max_concurrency: 16/max_concurrency: ${LIMIT}/" \
    /opt/paddleocr-server/PaddleOCR-VL-1.6.yaml > /tmp/pipeline-replicas.yaml
exec paddlex --serve --pipeline /tmp/pipeline-replicas.yaml --device gpu:0 --host 0.0.0.0 --port 8080
