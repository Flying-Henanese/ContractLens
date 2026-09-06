# 华为昇腾 NPU 部署

本配置适配 PaddleOCR-VL-1.6 的华为昇腾 910B 部署，沿用 CUDA 版本的双服务架构：

- `paddleocr-vl-api`：运行文档预处理和 PP-DocLayoutV3，默认使用物理 NPU 0。
- `paddleocr-vlm-server`：运行 vLLM VLM 服务，默认使用物理 NPU 1、2，并启动两个数据并行副本。

## 前置条件

- Linux 与 Docker Compose。
- 华为昇腾 910B，宿主机驱动和固件已正确安装。
- 宿主机可执行 `npu-smi info`。
- 宿主机存在 `/usr/local/Ascend/driver`、`/usr/local/bin/npu-smi` 和 `/usr/local/dcmi`。
- 默认需要 3 张可用 NPU。也可以只给 VLM 分配 1 张卡，并将 `VLM_DATA_PARALLEL_SIZE` 改为 `1`。

官方镜像内已包含与昇腾适配的 PaddlePaddle、自定义 NPU 插件及 vLLM 运行环境，不应替换为 NVIDIA 镜像。

## 启动

```bash
cp .env.ascend.example .env.ascend
```

按实际设备修改 `.env.ascend`。`VLM_NPU_IDS` 中的设备数量必须等于
`VLM_DATA_PARALLEL_SIZE`，且不应和 `PIPELINE_NPU_ID` 重叠。

```bash
docker compose --env-file .env.ascend -f compose.ascend.yaml config
docker compose --env-file .env.ascend -f compose.ascend.yaml pull
docker compose --env-file .env.ascend -f compose.ascend.yaml up -d
```

查看启动日志：

```bash
docker compose --env-file .env.ascend -f compose.ascend.yaml logs -f paddleocr-vlm-server
docker compose --env-file .env.ascend -f compose.ascend.yaml logs -f paddleocr-vl-api
```

检查服务：

```bash
curl http://127.0.0.1:8880/health
curl http://127.0.0.1:8880/docs
npu-smi info
```

停止服务：

```bash
docker compose --env-file .env.ascend -f compose.ascend.yaml down
```

## 常用调整

离线环境将两个镜像标签改为：

```dotenv
ASCEND_API_IMAGE_TAG=latest-huawei-npu-offline
ASCEND_VLM_IMAGE_TAG=latest-huawei-npu-offline
```

单张 VLM NPU：

```dotenv
PIPELINE_NPU_ID=0
VLM_NPU_IDS=1
VLM_DATA_PARALLEL_SIZE=1
```

若启动或压测时发生 HBM OOM，依次降低
`VLM_GPU_MEMORY_UTILIZATION`、`VLM_MAX_NUM_SEQS` 和输入并发。

容器通过 `ASCEND_RT_VISIBLE_DEVICES` 接收物理卡号。容器内只暴露被分配的设备，
所以 API 的启动参数固定使用 `npu:0`。

## 说明

该文件按 PaddleOCR 官方昇腾方案使用 `privileged: true`，并挂载宿主机 Ascend
driver、`npu-smi` 与 DCMI。若生产环境需要收紧权限，应在目标驱动版本和设备节点
上完成验证后，再改为显式 `devices` 映射。
