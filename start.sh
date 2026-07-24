CUDA_VISIBLE_DEVICES=6 \
uv run --frozen paddlex --serve \
  --pipeline ./PP-StructureV3-cuda.yaml \
  --device gpu:0 \
  --host 0.0.0.0 \
  --port 8888
