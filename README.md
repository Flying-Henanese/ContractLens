# paddleocr-server

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

## Docker Compose 部署

要求：Linux、Docker Compose、NVIDIA Container Toolkit，以及至少 3 张可用 GPU（默认 1 张用于 Pipeline，2 张用于 VLM）。

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
PIPELINE_GPU_ID=4
VLM_GPU_IDS=5,6
VLM_DATA_PARALLEL_SIZE=2
VLM_DATA_PARALLEL_BACKEND=mp
```

`VLM_GPU_IDS` 中的 GPU 数量必须等于 `VLM_DATA_PARALLEL_SIZE`。Pipeline GPU 不应与 VLM GPU 重叠。

启动：

```bash
docker compose up -d
docker compose logs -f paddleocr-vlm-server
docker compose logs -f paddleocr-vl-api
```

检查服务：

```bash
curl http://127.0.0.1:8880/health
curl http://127.0.0.1:8880/docs
```

解析接口：

```text
POST http://127.0.0.1:8880/layout-parsing
```

停止：

```bash
docker compose down
```

两个容器共用宿主机模型目录 `/home/mineru_dev/.paddlex`，并挂载到容器内 `/home/paddleocr/.paddlex`。执行 `docker compose down` 不会删除该宿主机目录中的模型。

## 使用现有 uv 环境启动

`start_vl.sh` 支持相同的环境变量，并会在启动前校验 GPU 数量与 DP 副本数：

```bash
PIPELINE_GPU_ID=4 \
VLM_GPU_IDS=5,6 \
VLM_DATA_PARALLEL_SIZE=2 \
VLM_DATA_PARALLEL_BACKEND=mp \
./start_vl.sh
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