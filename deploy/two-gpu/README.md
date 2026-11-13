# ContractLens 双 GPU 共置部署手册

适用：Linux x86_64，Docker Engine、Compose v2.30+（支持 !override）、NVIDIA 驱动和 NVIDIA Container Toolkit。
目标是两卡 V100；当前实测硬件是两张 T4，不能替代 V100 现场验收。V100 16GB/32GB 均须确认实际空闲显存。
PaddleOCR 官方提示 CC7.x 的 T4/V100 使用 vLLM 可能超时或 OOM：
https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html

当前T4验证：三轮固定样本48/48成功、严格校验通过，中位0.417页/s；
整书按用户要求提前停止，231条完成记录中223成功、8超时，存在GPU偏载。
未通过整书无超时验收，未执行业务网关真实解析烟测；V100需现场验收后再上线。

## 1. 交付物及边界

代码包包含 src、Dockerfile、依赖锁、Compose、推理入口、测试脚本和本手册，不包含 Docker 镜像层、模型权重、真实 PDF、解析正文、私钥或已配置 .env。
这是在线安装的源码交付包。离线环境必须事先准备下文所列镜像及完整模型缓存；只复制源码不能离线启动。
Ascend 配置未改动，本文所有命令只启用 CUDA。

## 2. GPU 拓扑与选择（重点）

```text
宿主 GPU A → pipeline-1 + vLLM rank 0（TP=1）
宿主 GPU B → pipeline-2 + vLLM rank 1（TP=1）
网关 → Nginx → 两个 Pipeline → 共享的 vLLM API（DP=2）
```

Pipeline 与 DP rank 只是物理共置，并非请求一对一绑定；共享 vLLM API 自行调度。
DP=2 是两个完整模型副本，显存不合并为一个大模型池。

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used --format=csv
cp deploy/two-gpu/env.template .env.two-gpu
```

编辑 `.env.two-gpu`：例如只有两卡时设 `COLOCATED_GPU_1=0`、`COLOCATED_GPU_2=1`；
多卡服务器选择宿主机 `nvidia-smi` 显示的两块空闲卡，如 `2` 与 `3`。两个值必须为不同的非负整数；入口会拒绝同卡或无效编号。
不要把容器内局部编号误作宿主编号：worker 容器只使用指定宿主卡，PaddleX 的 `gpu:0` 是可见设备的局部编号。
vLLM 可见列表按 A,B 顺序，rank0/1 分别使用该列表的第0/1块卡。
当前 Compose 向推理容器暴露所有 NVIDIA 设备，再由 CUDA_VISIBLE_DEVICES 选择；这是调度配置，不是安全隔离。
修改GPU、DP或显存参数后用 `up` 重建配置，不能只 `restart`。

## 3. 主机、缓存与镜像准备

建议预留至少 64GiB 主机内存和足够磁盘；镜像、模型缓存体积较大，应按实际下载量规划。
每个推理容器配置 `/dev/shm` 上限64GiB，并非启动时立即分配。共享内存总使用仍受宿主RAM限制。

```bash
docker version
docker compose version
nvidia-smi
sudo mkdir -p /srv/contractlens/cache/paddlex
# .env.two-gpu 的 PADDLEX_CACHE_DIR 必须指向实际缓存目录。
# NVIDIA runtime 基础检查（需要拉取该镜像）：
docker run --rm --gpus all nvidia/cuda:12.2.2-runtime-ubuntu22.04 nvidia-smi
```

驱动须兼容镜像实际使用的 CUDA 运行时；不能仅用网关 Dockerfile 的 CUDA12.2 推断推理镜像要求。
首次在线启动会下载模型，需网络、空间和可写缓存；受限网络可复制已经验证的完整 `.paddlex` 缓存，保留目录结构。
环境模板已固定本轮使用的 Pipeline、vLLM 镜像 digest；不要为了“最新”随意更换版本。
网关镜像名由 `PDF_PARSER_IMAGE` 指定，默认 `pdf-parser:two-gpu`，首次需构建。

```bash
bash scripts/docker-two-gpu.sh config
bash scripts/docker-two-gpu.sh build
bash scripts/docker-two-gpu.sh up
bash scripts/docker-two-gpu.sh ps
```

全程使用 `docker-two-gpu.sh` 入口，它固定加载基础、replicas、colocated 三份 Compose。
不要直接运行不带 overlay 的 `docker compose up`，也不要把本方案配置粘贴到 Ascend 环境。
不在宿主机运行 uv sync；Python 依赖在网关镜像构建时按 uv.lock 安装。
新服务器首次构建会访问基础镜像仓库及 Python 包源。

## 4. 参数与端口

| 配置 | 初始值 | 运维含义 |
| --- | --- | --- |
| COLOCATED_GPU_1 / COLOCATED_GPU_2 | 0 / 1 | 必改为宿主实际两张空闲卡 |
| VLM_GPU_MEMORY_UTILIZATION | 0.6 | 每卡vLLM预算比例，给Pipeline及CUDA上下文留余量；不是全进程硬上限 |
| VLM_MAX_NUM_SEQS | 16 | 每个DP rank最大序列数 |
| VLM_MAX_NUM_BATCHED_TOKENS | 16384 | 每rank调度token预算 |
| PIPELINE_SUBGRAPH_CONCURRENCY | 16 | 每worker子图请求并发 |
| PDF_PARSER_CONCURRENCY | 2 | 网关单文档逐页请求并发；压测独立客户端C8另行指定 |
| PDF_PARSER_RETRIES | 0 | 不自动重试，避免长尾请求重复占用 |
| PDF_PARSER_TIMEOUT_SECONDS | 120 | CLI默认单页超时；独立基准总超时120s；Nginx读空闲超时120s |
| PDF_PARSER_PORT / API_PORT / VLM_PORT | 8888 / 8880 / 8118 | 宿主端口；变更后运维检查URL也须修改 |

网关文档API当前固定总超时300s并覆盖单页超时设置；大PDF宜用CLI，API限时未作更改。
启动需要等待vLLM模型初始化，健康检查等待窗口默认900s。
最终应有5个健康服务：api、paddleocr-vl-api（Nginx）、pipeline-1、pipeline-2、paddleocr-vlm-server。
监听端口默认绑定宿主全部地址；按部署网络规划防火墙，尤其限制8118诊断接口的访问。

```bash
curl --fail http://127.0.0.1:8888/openapi.json >/dev/null
curl --fail http://127.0.0.1:8880/health
curl --fail http://127.0.0.1:8118/v1/models
bash scripts/docker-two-gpu.sh ps
nvidia-smi
```

健康只证明服务可达。V100 上还必须用实际 PDF 请求确认 sm70 内核、FP16和显存兼容性；
不能把T4成功推断为V100成功。当前镜像按设备自动选择dtype；如V100报BF16、FlashAttention或无适用kernel，
保存错误和镜像digest，停止上线并另行验证兼容镜像/后端，不要直接改产线默认配置。

## 5. 真实文档验收与性能复测

用户PDF不随代码包分发，按授权自行放到 `tmp/pdfs/book.pdf`。
完整流程也可用 `BENCHMARK_CLIENT_IMAGE=pdf-parser:two-gpu bash scripts/benchmark_two_gpu.sh unique-label`，
它先检查健康状态，再执行预热、三轮16页和一轮整书；默认端口不变才可直接使用。
将网关镜像名用于客户端（测试脚本从工作目录挂载），真实结果只写到output/smoke。

```bash
mkdir -p output/smoke tmp/pdfs
# 16页固定样本；run名称每次不同，已有结果目录不会覆盖。
docker run --rm --user "$(id -u):$(id -g)" --gpus all --network host \
  -v "$PWD:/work" -w /work -e PYTHONPATH=/work/src \
  --entrypoint python pdf-parser:two-gpu scripts/benchmark_replicas.py \
  --pdf tmp/pdfs/book.pdf --run acceptance-sample-1 \
  --pages 1,2,3,6,7,8,30,40,80,120,160,200,240,280,320,360 --concurrency 8
# 全407页独立请求：只有后端仍健康的超时才继续；有失败返回码1，未完整尝试返回2。
docker run --rm --user "$(id -u):$(id -g)" --gpus all --network host \
  -v "$PWD:/work" -w /work -e PYTHONPATH=/work/src \
  --entrypoint python pdf-parser:two-gpu scripts/benchmark_replicas.py \
  --pdf tmp/pdfs/book.pdf --run acceptance-full-1 --pages all --concurrency 8 --continue-timeout-pages
```

如修改镜像名或端口，以上命令须同步调整；基准脚本GPU遥测和vLLM指标默认8118。
独立页诊断可保留成功页，不代表网关文档部分成功；生产网关仍然fail-fast。
观察 summary.json、pages.jsonl、telemetry.jsonl：成功页/s、超时、严格校验、每rank Running/Waiting、GPU负载/显存峰值。
完整文档及API路径也须验收，不能只看独立页测试。异常页未解决前不得声称全书无损通过。
下面用运维自备的短PDF（例如同一测试文档前2页）检查网关路径：

```bash
# 准备 tmp/pdfs/smoke.pdf 后执行：
docker run --rm --user "$(id -u):$(id -g)" --network host \
  -v "$PWD:/work" -w /work -e PYTHONPATH=/work/src \
  --entrypoint pdf-parser pdf-parser:two-gpu parse tmp/pdfs/smoke.pdf \
  -o output/smoke/cli_result.json --endpoint http://127.0.0.1:8880 \
  --timeout 120 --retries 0 --concurrency 2
curl --fail --noproxy '*' --max-time 310 \
  -F 'file=@tmp/pdfs/smoke.pdf;type=application/pdf' \
  http://127.0.0.1:8888/api/v1/documents/parse -o output/smoke/api_result.json
for result in cli_result.json api_result.json; do
  docker run --rm --user "$(id -u):$(id -g)" \
    -v "$PWD:/work" -w /work --entrypoint python pdf-parser:two-gpu \
    .harness/scripts/validate_result.py "output/smoke/$result"
done
```

本次T4固定样本及整书结果见
[测试报告](../../.harness/reports/benchmarks/2026-11-13-two-gpu-colocated.md)。

## 6. 日常操作、排障与回滚

```bash
bash scripts/docker-two-gpu.sh ps
bash scripts/docker-two-gpu.sh logs
# 停止日志Ctrl-C不会停止容器。
bash scripts/docker-two-gpu.sh down
# 修改配置后重新启动：
bash scripts/docker-two-gpu.sh config
bash scripts/docker-two-gpu.sh up
```

发生OOM/启动失败时先保存有限日志、nvidia-smi、配置与版本，停止异常服务分析；
不要循环重启或继续加显存比例。共置环境不得沿用独占卡的0.8/0.9预算而不验证。
本轮可选overlay保留故障容器（restart=no），主机重启后运维需主动执行up并检查健康。
回滚须同时还原代码与环境配置。已有T4旧方案的 `.env` 不被此入口修改；
在两卡入口down后，按旧README显式设置replicas/4workers并使用scripts/docker.sh up恢复旧栈。
新服务器回滚到自己验收过的版本，不要引用T4宿主GPU编号。

## 7. 离线转移的额外准备

联网机器根据上述三份Compose导出实际镜像清单，准备网关、Pipeline、vLLM、Nginx镜像：

```bash
docker compose --env-file .env.two-gpu -f compose.yaml -f compose.replicas.yaml -f compose.colocated.yaml config --images
# docker save -o images.tar <清单中的所有镜像引用>
# 目标机器：docker load -i images.tar
```

同时转移完整PaddleX模型缓存并验证完整性，拷贝目标配置后config/up。
源码包不含images.tar或模型缓存。离线不能执行build --pull；需预先构建并导入网关镜像。
镜像digest及运行时引用须在目标主机 `docker image inspect` 和实际启动中复核。
