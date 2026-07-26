# AGENTS.md

## 项目定位

本项目用于构建 PaddleOCR-VL-1.6 高并发文档解析服务，已经在以下平台完成实际运行验证：

- NVIDIA CUDA
- 华为昇腾 NPU

项目的核心目标是用一个前道 PP-DocLayout/PaddleOCR API 服务拆分和调度任务，
再由后端多个 vLLM 模型实例并行完成版面子图识别，从而提高大批量文档的整体
吞吐能力。

项目不自行实现 OCR 推理框架，而是通过 PaddleX/PaddleOCR Pipeline、vLLM 和
Docker Compose 组织高并发处理链路。

主链路为：

1. 单个 PaddleOCR API/Pipeline 接收文档请求。
2. 前道 PP-DocLayoutV3 执行文档预处理、版面分析和子图裁剪。
3. Pipeline 将大量版面子图并发提交给后端 vLLM 服务。
4. vLLM 通过多个 PaddleOCR-VL-1.6-0.9B 模型实例和实例内连续批处理并行消费请求。
5. Pipeline 重组识别结果，并通过 `/layout-parsing` 返回。

这里的“多个 vLLM 实例”在当前实现中表现为同一个 vLLM API Server 后面的多个
数据并行模型副本（DP ranks）。它们是多个完整模型实例，不是多个独立对外端口
或多个 Compose 容器。除非用户明确要求改变架构，不要额外加入反向代理、Ray
Serve 或手工维护多个 VLM 地址。

## 重要原则

- 当前 CUDA 和昇腾配置均已通过实机验证，不要仅凭静态推断认定现有配置错误。
- 修改前先阅读 `README.md`；涉及昇腾时还必须阅读 `ASCEND.md`。
- 保持现有“单前道、后端多实例”的双服务架构：
  - 一个 `paddleocr-vl-api` 负责 API、预处理、PP-DocLayoutV3、子图分发和结果重组。
  - 一个 `paddleocr-vlm-server` 入口管理多个 PaddleOCR-VL 完整模型实例，并负责调度和连续批处理。
- 高并发能力依赖三层协同，不要只调整其中一个参数就宣称完成优化：
  - Pipeline 的版面子图并发：`max_concurrency`。
  - vLLM 单实例调度/连续批处理：`max-num-seqs`、`max-num-batched-tokens`。
  - vLLM 横向模型实例数：`data-parallel-size`。
- 不要把 Pipeline GPU/NPU 与 VLM GPU/NPU 分配到同一张物理设备。
- `VLM_GPU_IDS` 或 `VLM_NPU_IDS` 中的设备数量必须与 `VLM_DATA_PARALLEL_SIZE` 一致。
- 除非用户明确要求，不要升级镜像、PaddlePaddle、PaddleOCR、PaddleX、vLLM、Torch、Transformers 或其他推理依赖。
- 除非有目标硬件上的验证依据，不要擅自删除 CUDA/NCCL、昇腾设备挂载、`privileged`、共享内存或模型缓存相关配置。
- 不要直接修改用户的模型缓存目录或删除其中内容。
- 不要把本地生成的运行时配置、日志、模型或测试文档提交到版本库。

## 关键文件

- `compose.yaml`：NVIDIA CUDA Docker Compose 部署。
- `compose.ascend.yaml`：华为昇腾 Docker Compose 部署。
- `.env.example`：CUDA 环境变量示例。
- `.env.ascend.example`：昇腾环境变量示例。
- `PaddleOCR-VL-1.6.yaml`：PaddleOCR-VL Pipeline 配置。
- `vllm_config.yaml`：vLLM 推理与数据并行配置模板。
- `docker/vlm-entrypoint.sh`：CUDA VLM 容器入口。
- `docker/vlm-entrypoint-ascend.sh`：昇腾 VLM 容器入口。
- `start_vl.sh`：使用已有 uv 环境在宿主机启动 CUDA 服务。
- `scripts/benchmark.py`：`/layout-parsing` 接口并发压测工具。
- `PP-StructureV3-cuda.yaml`、`start.sh`：独立 PP-StructureV3 实验配置，不属于 PaddleOCR-VL 多实例主链路。

## 修改要求

### 通用

- 修改应尽量小而明确，避免无关重构和纯格式化改动。
- 保持配置项、环境变量、README 和示例文件之间一致。
- 新增环境变量时：
  - 提供合理默认值。
  - 更新对应的 `.env*.example`。
  - 更新相关文档。
  - CUDA 与昇腾共用的变量应保持相同命名和语义。
- Shell 脚本使用 Bash，并保持 `set -Eeuo pipefail`。
- 路径和变量必须加双引号，避免空格和通配符展开问题。
- 运行时配置应写入临时目录或 `logs/`，不要覆盖版本库中的配置模板。
- 错误信息应明确指出错误变量、当前值和正确约束。

### CUDA

- CUDA 设备通过 `CUDA_VISIBLE_DEVICES` 暴露。
- 容器内设备编号会重新映射，因此 Pipeline 使用 `gpu:0` 是预期行为。
- `tensor-parallel-size: 1` 表示每个 VLM 数据并行模型实例使用一张卡。
- 修改 NCCL 配置前，应考虑目标机器的 GPU 拓扑、P2P 和 IB 环境。

### 华为昇腾

- 昇腾设备通过 `ASCEND_RT_VISIBLE_DEVICES` 暴露。
- 容器内设备编号会重新映射，因此 Pipeline 使用 `npu:0` 是预期行为。
- 保留宿主机 Ascend driver、`npu-smi` 和 DCMI 的挂载，除非已有目标环境验证。
- `gpu-memory-utilization` 是 vLLM 沿用的参数名，在昇腾环境中表示 NPU HBM 使用比例。
- 昇腾相关修改必须同步检查 `ASCEND.md`、`.env.ascend.example` 和 `compose.ascend.yaml`。

## 验证要求

根据改动范围执行尽可能完整的验证。

### 最低静态检查

```bash
bash -n start.sh start_vl.sh \
  docker/vlm-entrypoint.sh \
  docker/vlm-entrypoint-ascend.sh

python3 -m py_compile scripts/benchmark.py

docker compose config --quiet

docker compose \
  --env-file .env.ascend.example \
  -f compose.ascend.yaml \
  config --quiet

git diff --check
```

### 运行验证

只有在目标服务器具备相应 GPU/NPU、驱动、镜像和模型环境时才执行完整启动验证。

CUDA：

```bash
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8880/health
curl --fail http://127.0.0.1:8880/openapi.json
```

昇腾：

```bash
docker compose \
  --env-file .env.ascend \
  -f compose.ascend.yaml \
  up -d

docker compose \
  --env-file .env.ascend \
  -f compose.ascend.yaml \
  ps

curl --fail http://127.0.0.1:8880/health
curl --fail http://127.0.0.1:8880/openapi.json
```

接口压测：

```bash
python scripts/benchmark.py ./demo.pdf \
  --base-url http://127.0.0.1:8880 \
  --concurrency 2 \
  --requests 4
```

不要在缺少目标硬件时将“未执行实机验证”描述为代码或配置失败。应清楚区分：

- 已完成的静态检查。
- 已完成的容器配置检查。
- 尚未执行的 CUDA 或昇腾实机验证。

## 高并发与性能调优

- 性能目标首先是大批量文档的稳定吞吐，其次才是单文档最低延迟。
- 一个文档可产生多个版面子图；足够的文档并发和子图并发才能让多个 VLM
  实例持续有任务可处理。
- 数据并行只直接扩展 VLM 识别阶段。单个 PP-DocLayout/API 前道服务、文档
  预处理、结果重组或 API 请求调度都可能成为端到端瓶颈。
- 调优时联合观察：
  - `VLRecognition.genai_config.max_concurrency`
  - `max-num-seqs`
  - `max-num-batched-tokens`
  - `gpu-memory-utilization`
  - `data-parallel-size`
- OOM 时优先降低显存/HBM 使用率、并发序列数、批处理 token 数或请求并发。
- 性能结论必须来自单实例与多实例、不同外层文档并发的对照压测，并结合
  GPU/NPU 利用率、错误率、端到端吞吐和尾延迟判断。
- 如果 VLM 设备利用率不足，先判断前道是否能持续生成足够多的子图任务。
- 如果 VLM 已饱和但端到端吞吐不再增长，应定位单个前道 API/PP-DocLayout
  是否成为瓶颈，而不是盲目增加模型实例。
- 不要仅根据模型大小或静态配置宣称吞吐提升比例。

## 提交与交付

- 不提交 `.env`、`.env.ascend`、日志、运行时 YAML、模型缓存或用户测试文件。
- 提交前检查 `git status`，保留并避开用户已有的无关改动。
- 汇报时说明：
  - 修改了哪些文件。
  - CUDA、昇腾或两者是否受到影响。
  - 实际执行了哪些检查。
  - 哪些验证因缺少目标硬件而未执行。
