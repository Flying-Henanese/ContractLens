# 华为昇腾 NPU 推理模块参考

`paddleocr-server/` 已导入 ContractLens 单仓库。它仍保存昇腾推理配置，但不再是
ContractLens 的独立部署项目。生产环境使用仓库根目录的统一生命周期。单 Pipeline 拓扑如下：

```text
ContractLens api -> PaddleX Pipeline -> PaddleOCR-VL / vLLM
```

不要在本目录执行 `docker compose -f compose.ascend.yaml up`：该历史双服务配置没有
ContractLens 网关，并可能与根 Compose 的服务名或端口冲突。

## 当前验证状态

根 Ascend Compose 已通过静态配置和脚本语法检查，但尚未在昇腾主机验证镜像、驱动挂载、启动、
健康检查或真实解析。此前的推理模块双服务验证（如有）仅是历史参考，不能作为根三服务栈已验证的
证据。

## 生产前置条件

- Linux、Docker Engine 与 Docker Compose v2。
- 兼容的昇腾 910B、驱动、固件和 NPU 容器运行环境。
- 宿主机可执行 `npu-smi info`，并提供 `/usr/local/Ascend/driver`、
  `/usr/local/bin/npu-smi` 与 `/usr/local/dcmi`。
- 已确认网关、PaddleX 与 vLLM 镜像可用，以及 `PADDLEX_CACHE_DIR` 存在且不得清理。
- 使用模板前，确认设备编号 `4,5,6,7` 可用。共卡模式每卡运行一个 Pipeline worker 和一个 vLLM rank。
  `single` 和 `replicas` 模式使用 NPU `7` 运行 Pipeline，使用 NPU `4,5,6` 运行三个 vLLM rank。
  使用其他编号时须核对容器可见编号和设备挂载的对应关系。

所选昇腾推理镜像预期提供适配的 PaddlePaddle、NPU 插件与 vLLM 运行环境；不要替换为
NVIDIA 镜像，并在目标主机上验证该预期。

## 根目录生产启动

从仓库根目录复制模板并按已核对的 NPU 分配调整环境文件：

```bash
cp .env.ascend.template .env.ascend
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
```

首次启动或网关 `pyproject.toml`、`uv.lock`、Dockerfile、镜像构建参数变化时才构建网关镜像：

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh build
```

无论是否构建，都通过同一入口启动并检查所选拓扑的服务。

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh up
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh ps
```

确认网关 `http://127.0.0.1:8888/openapi.json`、PaddleX
`http://127.0.0.1:8880/health`、各容器的 healthy 状态与 `npu-smi info`。vLLM 的
healthcheck 本身请求容器内 `/v1/models`。根 Ascend Compose 不发布 `8118`，需要诊断该端点时，
通过对应 vLLM 容器内的请求检查。随后使用一个获准的真实输入执行解析烟测。异常时读取对应服务的
有限日志，不循环重启。

## 推理配置说明

根 [Compose](../compose.ascend.yaml) 的基础推理容器使用特权模式，通过
`ASCEND_RT_VISIBLE_DEVICES` 选择运行时设备。副本 overlay 的 worker 默认以
`ASCEND_PRIVILEGED=false` 运行，并显式挂载 NPU 和管理设备。
普通副本模式使用 `PIPELINE_NPU_ID` 选择设备节点，worker 的 CANN 可见编号固定为 `3`。
四卡共卡模式可以分别配置每个 worker 的设备节点和可见编号。Pipeline 在容器内使用 `npu:0`。

本目录的 `compose.ascend.yaml` 仅保留为导入前的推理模块参考，不能替代上述根目录流程。

## 多 Pipeline 静态适配

此功能尚未在昇腾主机验证。需要 Docker Compose >= 2.24.4（支持 `!override`）。
Nginx 模板需要 Nginx >= 1.27.3；默认 `nginx:1.29.7-alpine`，直接由 Compose 拉取，
没有自定义 Dockerfile。ARM/x86 主机应核对所选标签或 digest 的 CPU 架构。
可通过 `PIPELINE_PROXY_IMAGE` 固定目标架构或多架构索引 digest。

复制根 `.env.ascend.template` 到 `.env.ascend`，设置：

```dotenv
CONTRACTLENS_PIPELINE_MODE=replicas
CONTRACTLENS_PIPELINE_WORKERS=2
PIPELINE_SUBGRAPH_CONCURRENCY=16
```

脚本读取 `.env.ascend` 中的模式和副本数。Shell 中同名的非空变量可临时覆盖文件值。

```bash
export CONTRACTLENS_PLATFORM=ascend
bash scripts/docker.sh config
bash scripts/docker.sh up
bash scripts/docker.sh ps
```

默认多个 Pipeline 共享 NPU 7，VLM 保持 NPU 4/5/6、DP=3。
副本没有独立宿主机端口。应核对 `PIPELINE_NPU_ID` 对应的设备和固定可见编号，确保
普通副本的物理设备与 VLM 分离。
所有 worker 继承当前 Ascend 驱动、缓存与设备管理挂载，网关仍连接原服务名。
Nginx 不挂载 NPU，不自动重发 POST，读取超时为 120 秒。

同事验收：先核对镜像、驱动、设备、端口和共享 NPU 内存容量；启动后确认全部容器健康，
检查网关 `/openapi.json`、代理 `/health`、容器内 VLM `/v1/models`，再执行真实 PDF
烟测和并发测试，核对结果质量、超时、NPU 内存与重启次数。静态检查不代表这些项目通过。
真实结果仅写入 `output/smoke/`。网关重试仍由原有 `PDF_PARSER_RETRIES` 控制。

恢复单 Pipeline 时，将 env 文件中的模式设为 `single`，然后运行 `bash scripts/docker.sh up`。
统一入口会恢复原 Pipeline 服务并移除副本，无需手动启动或停止独立容器。

## 四卡共卡部署

每张卡运行一个 PaddleX worker 和一个 vLLM rank。四个 worker 共用
`http://paddleocr-vlm-server:8118/v1`。单个 vLLM API Server 以 `TP=1`、`DP=4`、`mp`
启动并在四个 rank 间分发版面块。Nginx 继续在四个 PaddleX worker 间分发文档请求。

模板已经设置 `CONTRACTLENS_PIPELINE_MODE=colocated` 和三组卡号。复制成 `.env.ascend` 后，
在仓库根目录运行以下命令检查配置。

```bash
export CONTRACTLENS_PLATFORM=ascend
bash scripts/docker.sh config
bash scripts/docker.sh config --format json
```

`CONTRACTLENS_COLOCATED_NPU_IDS` 按 `pipeline-1` 到 `pipeline-4` 的顺序指定宿主机
`/dev/davinciN` 设备。若 CANN 的可见编号与设备文件编号不同，使用下列变量表达各自的编号，
两个列表的每个位置都要指向物理列表同一位置的卡。
脚本按 CANN 要求对传给 vLLM 的可见编号做数值升序排列，worker 的设备分配按原顺序。
普通副本模式曾用 `/dev/davinci7` 配合可见编号 `3`，请按现场映射确认共卡变量。
[华为 CANN 可见设备说明](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/maintenref/envvar/envref_07_0028.html)

| 环境变量 | 用途 | 未设置时 |
| --- | --- | --- |
| `CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS` | 各独立 worker 容器中的 CANN 可见编号。独立容器的编号可以重复 | 沿用物理列表 |
| `CONTRACTLENS_COLOCATED_VLM_RT_IDS` | vLLM 容器中四张卡的 CANN 可见编号，四个编号必须不同 | 沿用物理列表 |

现场确认设备编号后，在同一 Shell 执行 `bash scripts/docker.sh up` 和 `bash scripts/docker.sh ps`。
用 `npu-smi info` 核对每张物理卡上的 PaddleX 和 vLLM 进程，检查 `/v1/models`，再用代表性 PDF
验证完整页数、耗时、各 rank 的负载和每张卡的 HBM 峰值。当前共卡模式仅通过静态配置检查。

恢复分卡部署时，将 `CONTRACTLENS_PIPELINE_MODE` 切回 `replicas` 或 `single`，按原配置运行
`bash scripts/docker.sh up`。`VLM_NPU_IDS` 和 `VLM_DATA_PARALLEL_SIZE` 将重新从原配置读取。

## 网关镜像构建：文件描述符不足

若 `uv python install` 在标准库字节码编译时报 `No file descriptors available
(os error 24)`，表示构建进程触及文件描述符上限；不是 PaddleOCR 或 NPU 推理错误。
`Dockerfile.ascend` 关闭可选的 uv 字节码预编译（`UV_COMPILE_BYTECODE=0`），
避免该编译阶段；依赖和 Python 版本保持原配置。未预编译可能增加 Python 冷启动耗时。
修改后在保留 Ascend 平台和副本环境变量的终端执行：

```bash
bash scripts/docker.sh build
bash scripts/docker.sh up
```

无需清空模型缓存或全量禁用 Docker 构建缓存。此变更仍需目标 ARM 构建器重建验证；
若其他阶段也出现同类错误，应进一步检查构建器进程的 nofile 限制。
