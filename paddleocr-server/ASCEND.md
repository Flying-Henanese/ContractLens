# 华为昇腾 NPU 推理模块参考

`paddleocr-server/` 已导入 ContractLens 单仓库。它仍保存昇腾推理配置，但不再是
ContractLens 的独立部署项目。生产环境必须从仓库根目录启动三服务栈：

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
- 根默认需要设备编号 `4,5,6,7` 可用：Pipeline 使用 NPU `7`，三个 VLM 数据并行副本使用
  NPU `4,5,6`。设备编号不同的主机必须先调整环境文件；Pipeline 设备不得和 VLM 设备重叠，
  且 VLM 设备数必须等于 `VLM_DATA_PARALLEL_SIZE`。

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

无论是否构建，都通过同一入口启动并检查三个服务：

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh up
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh ps
```

确认网关 `http://127.0.0.1:8888/openapi.json`、PaddleX
`http://127.0.0.1:8880/health`、三个容器的 healthy 状态与 `npu-smi info`；vLLM 的
healthcheck 本身请求容器内 `/v1/models`。根 Ascend Compose 不发布 `8118`，需要诊断该端点时，
通过对应 vLLM 容器内的请求检查。随后使用一个获准的真实输入执行解析烟测。异常时读取对应服务的
有限日志，不循环重启。

## 推理配置说明

根 [`compose.ascend.yaml`](../compose.ascend.yaml) 保留昇腾专有的 `privileged`、driver、
`npu-smi`、DCMI 挂载和 `ASCEND_RT_VISIBLE_DEVICES`。Pipeline 在容器内使用 `npu:0`，
因为可见物理设备会被重新编号。两个推理服务以只读方式挂载整个本目录，因此
`docker/vlm-entrypoint-ascend.sh`、`PaddleOCR-VL-1.6.yaml` 和 `vllm_config.yaml` 仍是
推理配置事实源。

本目录的 `compose.ascend.yaml` 仅保留为导入前的推理模块参考，不能替代上述根目录流程。
