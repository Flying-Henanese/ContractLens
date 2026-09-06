# Runtime And Configuration

## 支持环境

### CUDA

- Linux
- Docker Compose
- NVIDIA 驱动及 NVIDIA Container Toolkit
- 默认 1 张 Pipeline GPU 和 2 张 VLM GPU

### 华为昇腾

- Linux
- Docker Compose
- 华为昇腾 910B 及匹配的驱动、固件和容器镜像
- 宿主机提供 Ascend driver、`npu-smi` 和 DCMI

昇腾存在两组不同的当前默认值：

- 直接使用 `compose.ascend.yaml`，不传 env 文件且工作目录没有自动加载的
  `.env` 时：Pipeline NPU `0`，VLM NPU `1,2`，DP 为 `2`，HBM 使用比例为
  `0.8`。
- 使用文档推荐的 `.env.ascend.example` 时：Pipeline NPU `7`，VLM NPU
  `4,5,6`，DP 为 `3`，HBM 使用比例为 `0.3`。

因此“昇腾默认配置”必须注明是否加载了 `.env.ascend.example`，不能混用两组
数值。

## 关键环境变量

通用：

- `API_PORT`
- `VLM_MODEL`
- `VLM_DATA_PARALLEL_SIZE`
- `VLM_DATA_PARALLEL_BACKEND`
- `VLM_GPU_MEMORY_UTILIZATION`
- `VLM_MAX_NUM_SEQS`
- `VLM_MAX_NUM_BATCHED_TOKENS`
- `STARTUP_TIMEOUT`

CUDA：

- `API_IMAGE_TAG`
- `VLM_IMAGE_TAG`
- `PIPELINE_GPU_ID`
- `VLM_GPU_IDS`

昇腾：

- `ASCEND_API_IMAGE_TAG`
- `ASCEND_VLM_IMAGE_TAG`
- `PADDLEX_CACHE_DIR`
- `PIPELINE_NPU_ID`
- `VLM_NPU_IDS`

## 配置分层

1. `.env.example` 或 `.env.ascend.example` 提供部署参数样例。
2. Compose 将参数传入容器并声明设备、挂载和健康检查。
3. VLM entrypoint 校验设备数量和并行模型实例数。
4. entrypoint 以 `vllm_config.yaml` 为模板生成临时配置。它检查 DP 正整数、
   backend 和 VLM 可见设备数量，但 Compose 路径不检查 Pipeline/VLM 设备重叠。
5. `PaddleOCR-VL-1.6.yaml` 定义 Pipeline 模块、VLM 服务地址和 Pipeline 顶层
   并发参数：
   - `use_queues: True`：启用输入、CV、VLM 阶段之间的内部队列流水线。
   - `layout_prep_cpu_workers: 16`：只有支持该字段的 PaddleX 才会启用页面级
     CPU 准备线程池；旧版本会忽略。

不要把生成的临时配置反向写回模板。

并发参数之间的关系和调优顺序见 `concurrency-model.md`。

## 常用入口

CUDA Compose：

```bash
cp .env.example .env
docker compose up -d
```

昇腾 Compose：

```bash
cp .env.ascend.example .env.ascend
docker compose --env-file .env.ascend -f compose.ascend.yaml up -d
```

已有 uv 环境：

```bash
bash start_vl.sh
```

`start_vl.sh` 在 Git 中当前是 `100644`，没有可执行位，因此文档应使用
`bash start_vl.sh`。该宿主机入口会检查 Pipeline GPU 与 VLM GPU 是否重叠。

压测：

```bash
python scripts/benchmark.py ./demo.pdf \
  --base-url http://127.0.0.1:8880 \
  --concurrency 2 \
  --requests 4
```

## 本地验证限制

Compose 配置解析不等于目标硬件上的推理验证，也不会执行容器 entrypoint 的
设备数量检查或 Pipeline/VLM 重叠检查。缺少 Docker、GPU/NPU、驱动、模型缓存
或网络时，只报告已经完成的静态检查，不将环境缺失描述为配置故障。

两个平台默认使用可变的 `latest-*` 镜像标签。涉及运行时内部行为时，必须记录
镜像 ID/digest 和包版本，不能只引用标签名。
