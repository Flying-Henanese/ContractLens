# 华为昇腾 NPU 推理模块参考

`paddleocr-server/` 已导入 ContractLens 单仓库。它仍保存昇腾推理配置，但不再是
ContractLens 的独立部署项目。生产环境使用仓库根目录的统一生命周期。默认拓扑如下：

```text
ContractLens api -> Nginx -> 4 个 PaddleX worker -> PaddleOCR-VL / vLLM
```

不要在本目录执行 `docker compose -f compose.ascend.yaml up`：该历史双服务配置没有
ContractLens 网关，并可能与根 Compose 的服务名或端口冲突。

## 当前验证状态

根 Ascend Compose 已通过静态配置和脚本语法检查，但尚未在昇腾主机验证镜像、驱动挂载、启动、
健康检查或真实解析。此前的推理模块双服务验证（如有）仅是历史参考，不能作为统一部署已验证的
证据。

## 生产前置条件

- Linux、Docker Engine 与 Docker Compose 2.24.4 或更高版本。
- 兼容的昇腾 910B、驱动、固件和 NPU 容器运行环境。
- 宿主机可执行 `npu-smi info`，并提供 `/usr/local/Ascend/driver`、
  `/usr/local/bin/npu-smi` 与 `/usr/local/dcmi`。
- 已确认网关、PaddleX 与 vLLM 镜像可用，以及 `PADDLEX_CACHE_DIR` 存在且不得清理。
- 默认需要设备编号 `4,5,6,7` 可用。Pipeline 使用 NPU `7`，三个 VLM 数据并行副本使用
  NPU `4,5,6`。其他设备编号须核对环境变量和 Compose 的挂载映射。Pipeline 与 VLM 使用不同物理设备，
  VLM 设备数须等于 `VLM_DATA_PARALLEL_SIZE`。

所选昇腾推理镜像预期提供适配的 PaddlePaddle、NPU 插件与 vLLM 运行环境；不要替换为
NVIDIA 镜像，并在目标主机上验证该预期。

## 根目录生产启动

首次部署时，从仓库根目录将 `.env.ascend.template` 复制成 `.env`。若已有 `.env`，
合并本机配置，并确认 `CONTRACTLENS_PLATFORM=ascend`。旧 `.env.ascend` 中的设备、
端口和缓存设置一并迁移到 `.env`。迁移到四副本时，将旧模板的 `single` 和 `2`
更新为 `CONTRACTLENS_PIPELINE_MODE=replicas` 和 `CONTRACTLENS_PIPELINE_WORKERS=4`。
移除 Shell 中旧的同名 export 设置，让 Compose 使用 `.env` 中的值。

```bash
bash scripts/docker.sh config
```

首次启动或网关 `pyproject.toml`、`uv.lock`、Dockerfile、镜像构建参数变化时才构建网关镜像：

```bash
bash scripts/docker.sh build
```

通过同一入口启动并检查所选拓扑中的全部服务：

```bash
bash scripts/docker.sh up
bash scripts/docker.sh ps
```

确认网关 `http://127.0.0.1:8888/openapi.json`、PaddleX
`http://127.0.0.1:8880/health`、全部容器的 healthy 状态与 `npu-smi info`；vLLM 的
healthcheck 本身请求容器内 `/v1/models`。根 Ascend Compose 不发布 `8118`，需要诊断该端点时，
通过对应 vLLM 容器内的请求检查。随后使用一个获准的真实输入执行解析烟测。异常时读取对应服务的
有限日志，不循环重启。

## 推理配置说明

[`compose.replicas.ascend.yaml`](../compose.replicas.ascend.yaml) 中的 Pipeline worker 默认以
`ASCEND_PRIVILEGED=false` 运行，显式挂载 NPU 及管理设备、添加 `SYS_PTRACE`，
并挂载驱动、`npu-smi`、DCMI、`/etc/ascend_install.info` 和 `/var/log/npu`。
需要回滚权限模式时，在根 `.env` 中设置
`ASCEND_PRIVILEGED=true`，再运行统一入口的 `up`。显式设备挂载仍然保留。

[`compose.ascend.single.yaml`](../compose.ascend.single.yaml) 通过 `PIPELINE_NPU_ID` 和
`VLM_NPU_IDS` 设置单 Pipeline 和 vLLM 的可见设备。副本 overlay 通过 `PIPELINE_NPU_ID`
选择 worker 的宿主机设备挂载，容器内可见编号目前固定为 `3`。PaddleX 使用 `npu:0`，
需在目标主机核对设备映射。
Pipeline 和 vLLM 均从各自的只读目录挂载读取本模块的入口与配置。

本目录的 `compose.ascend.yaml` 仅保留为导入前的推理模块参考，不能替代上述根目录流程。

## 多 Pipeline 静态适配

此功能尚未在昇腾主机验证。需要 Docker Compose >= 2.24.4（支持 `!override`）。
Nginx 模板需要 Nginx >= 1.27.3；默认 `nginx:1.29.7-alpine`，直接由 Compose 拉取，
没有自定义 Dockerfile。ARM/x86 主机应核对所选标签或 digest 的 CPU 架构。
可通过 `PIPELINE_PROXY_IMAGE` 固定目标架构或多架构索引 digest。

昇腾默认四个 Pipeline worker。需要选择副本数时，在根 `.env` 中设置：

```dotenv
CONTRACTLENS_PIPELINE_MODE=replicas
CONTRACTLENS_PIPELINE_WORKERS=4
```

设为 `2` 可切换到两副本。修改后运行 `bash scripts/docker.sh config` 和
`bash scripts/docker.sh up` 应用拓扑。

默认多个 Pipeline 共享 NPU 7，VLM 保持 NPU 4/5/6、DP=3。
副本没有独立宿主机端口。worker 使用的宿主机 NPU 必须存在且不能与 VLM 重叠，
启动前核对实际设备映射。
所有 worker 继承当前 Ascend 驱动、缓存与设备管理挂载，网关仍连接原服务名。
Nginx 不挂载 NPU，不自动重发 POST，读取超时为 1200 秒。

同事验收：先核对镜像、驱动、设备、端口和共享 NPU 内存容量；启动后确认全部容器健康，
检查网关 `/openapi.json`、代理 `/health`、容器内 VLM `/v1/models`，再执行真实 PDF
烟测和并发测试，核对结果质量、超时、NPU 内存与重启次数。静态检查不代表这些项目通过。
真实结果仅写入 `output/smoke/`。网关重试仍由原有 `PDF_PARSER_RETRIES` 控制。

恢复单 Pipeline 时，将根 `.env` 中的 `CONTRACTLENS_PIPELINE_MODE` 设为 `single`，
运行 `bash scripts/docker.sh up`。停机使用 `bash scripts/docker.sh down`，它也会清理
同项目下旧拓扑残留的容器。

## 网关镜像构建：文件描述符不足

若 `uv python install` 在标准库字节码编译时报 `No file descriptors available
(os error 24)`，表示构建进程触及文件描述符上限；不是 PaddleOCR 或 NPU 推理错误。
`Dockerfile.ascend` 关闭可选的 uv 字节码预编译（`UV_COMPILE_BYTECODE=0`），
避免该编译阶段；依赖和 Python 版本保持原配置。未预编译可能增加 Python 冷启动耗时。
修改后使用根 `.env` 的昇腾配置执行：

```bash
bash scripts/docker.sh build
bash scripts/docker.sh up
```

无需清空模型缓存或全量禁用 Docker 构建缓存。此变更仍需目标 ARM 构建器重建验证；
若其他阶段也出现同类错误，应进一步检查构建器进程的 nofile 限制。
