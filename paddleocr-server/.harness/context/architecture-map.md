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

The diagram shows the default single-Pipeline topology. In Ascend replica or
colocated mode, `paddleocr-vl-api` is Nginx and forwards requests to the Pipeline workers.
Workers wait for VLM health, Nginx waits for worker health, and the gateway waits
for Nginx health. The root lifecycle helper manages all services selected by the
[root topology](../../../.harness/architecture/README.md#compose-拓扑).

## Inference-module boundary

This module owns `PaddleOCR-VL-1.6.yaml`, the CUDA VLM configuration template,
and the inference startup scripts. Root Compose mounts the complete directory read-only at
`/opt/paddleocr-server` in Pipeline and vLLM containers. `PaddleOCR-VL-1.6.yaml` keeps
the VLM URL at `http://paddleocr-vlm-server:8118/v1`.

The local two-service Compose files omit the gateway and are retained only as
historical configuration references. They are not valid ContractLens production
topologies.

## Device mapping

- CUDA uses `CUDA_VISIBLE_DEVICES`; the one visible Pipeline device is addressed as
  `gpu:0` inside its container.
- The base Ascend services use privileged containers with `ASCEND_RT_VISIBLE_DEVICES`.
  The replica overlay sets explicit worker device mounts. A Pipeline process addresses
  its visible NPU as `npu:0`. See the [current mappings](runtime-and-config.md#huawei-ascend).
- VLM device-list length must equal `VLM_DATA_PARALLEL_SIZE`. Pipeline and VLM use
  separate physical devices by default. Ascend colocated mode puts one worker and
  one VLM rank on each selected card.

Static configuration cannot establish device availability or runtime compatibility.
The root Ascend topology remains unverified on target hardware.
