# paddleocr-server

## ContractLens production boundary

This directory is an imported inference module, not the production deployment
entry point. From the ContractLens repository root, use `scripts/docker.sh` with
the root `compose.yaml` or `compose.ascend.yaml`; it manages the gateway, PaddleX,
and vLLM as one lifecycle. The local Compose and host-start examples below are
historical inference-only references. Do not use them to deploy ContractLens: they
omit the gateway and can conflict with the root services and ports.

For the current Ascend production workflow and verification status, see
[`ASCEND.md`](ASCEND.md) and [`../docs/container-deployment.md`](../docs/container-deployment.md).

一个 PaddleOCR-VL-1.6 服务化部署示例：使用单个 PP-DocLayoutV3 Pipeline 完成版面分析，再将裁剪后的版面子图并发发送给多个 vLLM 数据并行副本。

## 架构

```text
POST /layout-parsing
        |
        v
PaddleOCR-VL Pipeline                         物理 GPU 4
  - 文档预处理
  - PP-DocLayoutV3
  - 裁剪和结果重组
        |
        | 多个并发的子图请求（max_concurrency）
        v
vLLM OpenAI-compatible API                   端口 8118
  - Data Parallel rank 0 / 完整 VLM 副本      物理 GPU 5
  - Data Parallel rank 1 / 完整 VLM 副本      物理 GPU 6
```

Pipeline 只配置一个 `server_url`。vLLM 在该 URL 后面启动多个 `PaddleOCR-VL-1.6-0.9B` 副本并负责请求调度，不需要额外的反向代理或 Ray Serve。

## 关键配置

`vllm_config.yaml`：

```yaml
tensor-parallel-size: 1
data-parallel-size: 2
data-parallel-backend: mp
```

- `tensor-parallel-size: 1`：每个 0.9B 模型副本使用一张 GPU。
- `data-parallel-size: 2`：启动两个完整模型副本。
- `data-parallel-backend: mp`：在单机上使用多进程管理副本。

`PaddleOCR-VL-1.6.yaml` 中的 `VLRecognition.genai_config.max_concurrency` 控制 Pipeline 同时提交多少个版面子图。它和 vLLM 的 `max-num-seqs`、副本数需要一起压测。

## 历史推理模块 Compose 参考（非 ContractLens 部署入口）

本目录保留的两个 Compose 文件反映导入前的 Pipeline/VLM 配置关系，但其旧环境模板
并未作为 ContractLens 文件提供，也不启动网关。不要执行这些旧命令；生产环境中的设备、
缓存和镜像参数应从根 `.env.template` 或 `.env.ascend.template` 设置，并由根 Compose
统一编排。

## 历史宿主机 uv 启动参考（非 ContractLens 部署入口）

`start_vl.sh` 支持相同的环境变量，并会在启动前校验 GPU 数量与 DP 副本数：

```bash
PIPELINE_GPU_ID=4 \
VLM_GPU_IDS=5,6 \
VLM_DATA_PARALLEL_SIZE=2 \
VLM_DATA_PARALLEL_BACKEND=mp \
bash start_vl.sh
```

脚本不会修改版本库中的 YAML，而是在 `logs/` 下生成本次启动使用的运行时配置。Pipeline 的 VLM 地址会自动替换为 `127.0.0.1:8118/v1`。

## 并发压测

压测脚本只使用 Python 标准库：

```bash
python scripts/benchmark.py ./demo.jpg \
  --base-url http://127.0.0.1:8880 \
  --concurrency 2 \
  --requests 4
```

建议依次测试：

```bash
python scripts/benchmark.py ./demo.pdf --concurrency 1 --requests 4
python scripts/benchmark.py ./demo.pdf --concurrency 2 --requests 4
python scripts/benchmark.py ./demo.pdf --concurrency 4 --requests 8
```

同时观察 GPU：

```bash
watch -n 1 nvidia-smi
```

两个 VLM GPU 都应加载一份模型，并在有足够版面子图或并发文档时产生计算负载。

## 调优顺序

1. 保持 `tensor-parallel-size: 1`，确认每张 VLM GPU 各有一个模型副本。
2. 从 `max_concurrency: 16`、`max-num-seqs: 16` 开始。
3. 逐步提高压测并发，确认两个 VLM GPU 是否同时工作。
4. GPU 利用率不足时，提高 Pipeline 的 `max_concurrency`。
5. vLLM 排队明显但显存充足时，提高 `max-num-seqs`。
6. OOM 时先降低 `gpu-memory-utilization`、`max-num-seqs` 或输入并发。

## 性能边界

数据并行只加速 VLM 识别阶段。当文档版面元素很少、PP-DocLayoutV3 成为瓶颈，或者外层 `paddlex --serve` 串行处理请求时，增加 VLM 副本不会线性提升端到端速度。应以 `scripts/benchmark.py` 的单副本/双副本对照结果判断实际收益。

## 其他文件

- `PP-StructureV3-cuda.yaml` 和 `start.sh` 保留为独立 PP-StructureV3 实验配置，不参与上述 PaddleOCR-VL 多副本链路。
- `docker/vlm-entrypoint.sh` 根据 `.env` 生成容器内运行时 vLLM 配置，并在副本数与 GPU 数量不一致时拒绝启动。
