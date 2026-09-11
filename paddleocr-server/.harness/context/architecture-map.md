# Architecture Map

## Production components

```text
ContractLens api (:8888, business API)
  -> paddleocr-vl-api (:8080 inside Compose, PaddleX Pipeline)
       -> paddleocr-vlm-server (:8118 inside Compose, vLLM DP ranks)
```

- The root `api` validates inputs and normalizes public output. It calls only
  `http://paddleocr-vl-api:8080` inside the Compose network.
- `paddleocr-vl-api` performs document preprocessing, PP-DocLayoutV3 analysis,
  crop preparation, request fan-out, and result assembly.
- `paddleocr-vlm-server` exposes one OpenAI-compatible internal API and schedules
  complete PaddleOCR-VL model instances through data parallelism.

Root Compose waits for VLM health before Pipeline startup and Pipeline health before
gateway startup. The root lifecycle helper starts, stops, restarts, and inspects all
three services together.

## Inference-module boundary

This module owns `PaddleOCR-VL-1.6.yaml`, `vllm_config.yaml`, and the VLM
entrypoints. Root Compose mounts the complete directory read-only at
`/opt/paddleocr-server` in both inference containers. `PaddleOCR-VL-1.6.yaml` keeps
the VLM URL at `http://paddleocr-vlm-server:8118/v1`.

The local two-service Compose files omit the gateway and are retained only as
historical configuration references. They are not valid ContractLens production
topologies.

## Device mapping

- CUDA uses `CUDA_VISIBLE_DEVICES`; the one visible Pipeline device is addressed as
  `gpu:0` inside its container.
- Ascend uses `ASCEND_RT_VISIBLE_DEVICES`; the one visible Pipeline device is
  addressed as `npu:0`. Root Ascend Compose preserves `privileged`, driver,
  `npu-smi`, and DCMI mounts.
- VLM device-list length must equal `VLM_DATA_PARALLEL_SIZE`, and Pipeline/VLM
  physical devices must not overlap.

Static configuration cannot establish device availability or runtime compatibility.
The root Ascend topology remains unverified on target hardware.
