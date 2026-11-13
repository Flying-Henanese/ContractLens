# Architecture

## 系统边界与当前数据流

当前仓库是一个单仓库、单次 Compose 发布的文档解析产品，而不是 `main` 分支时两个独立部署的
服务：根目录 `src/pdf_parser/` 是业务网关，`paddleocr-server/` 是随仓库交付但保持独立职责的
推理配置模块。它们不共享 Python 环境、模型实现或硬件配置，却由根目录 Compose 作为同一套运行时
进程启动和停止。

网关代码不承载模型推理：文档 API 当前接受 PDF 或受支持图像；CLI 仍只接受 PDF。根目录
Compose 同时启动网关、`paddleocr-server/` 中的 PaddleX Pipeline 和其 vLLM 进程，网关通过
Compose 服务 DNS `http://paddleocr-vl-api:8080` 请求 Pipeline。PDF 仍采用逐页远端请求，整份
PDF 提交是 active plan 中尚未落地的目标状态。

```text
外部调用方
  -> api（根目录网关；业务 API）
       -> paddleocr-vl-api（PaddleX Pipeline；Compose 内部 DNS）
            -> paddleocr-vlm-server（PaddleOCR-VL / vLLM）
```

`API_PORT` 和 CUDA 的 `VLM_PORT` 目前仍保留宿主机诊断映射，但它们不是业务调用契约；网关
不得直接调用 vLLM。推理容器将整个 `./paddleocr-server` 只读挂载到
`/opt/paddleocr-server`，因此入口脚本与 Pipeline 配置始终来自导入模块，而不是网关镜像。

```text
本地 PDF
  -> service.py::_count_pages：读取 PDF，校验加密/空/损坏并取得总页数
  -> ingestion/pdf.py：再次读取和校验，再拆成带 1-based 页码的单页 PDF
  -> service.py：按 Settings.concurrency 有界分批
  -> clients/paddlex.py：每页 POST /layout-parsing，要求恰好返回一页
  -> normalization/paddlex.py：按当前回退规则完成页面、OCR、版面和表格归一化
  -> normalization/seal.py：逐项绑定印章结果/区域，生成坐标、编号和正文引用
  -> service.py：恢复 page_num 顺序并组装 ParseResponse
  -> cli.py / api.py：文件或 HTTP 交付边界

本地图像（BMP/JPEG/PNG/TIFF/WEBP）
  -> api.py：按扩展名和 Content-Type 选择图像路径，并校验文件非空和二进制签名
  -> ingestion/image.py：识别受支持的图像格式
  -> service.py：读取并再次校验图像，作为单页文档编排
  -> clients/paddlex.py：一次 POST /layout-parsing，使用 fileType=1 并要求恰好返回一页
  -> normalization/paddlex.py / normalization/seal.py：复用页面归一化和印章处理
  -> service.py / api.py：组装 page_num=1 的 ParseResponse 并同步返回
```

跨页表格候选检测是对已生成结果 JSON 的独立只读分析，不在上述主解析链路中。

部署链路为 `api -> paddleocr-vl-api -> paddleocr-vlm-server`：`api` 等待 Pipeline 健康，
Pipeline 等待 vLLM 健康，三个进程由根 `compose.yaml`（CUDA）或 `compose.ascend.yaml`（Ascend）
和 `scripts/docker.sh` 一起启动、重启和停止。推理配置保持在 `paddleocr-server/`，而不是复制到
网关 Python 模块中。

正文回退、普通元素/印章坐标和印章去重能力等稳定行为只在 [`invariants.md`](invariants.md)
定义，本页不复制规则细节。

## 模块职责

| 关注点 | 权威模块 | 对应离线测试 |
| --- | --- | --- |
| FastAPI 的 PDF/图像上传、同步路由、超时和 HTTP 错误 | `src/pdf_parser/api.py` | `tests/test_api.py`、`tests/test_api_timeout.py` |
| CLI 参数、输出路径、终端消息 | `src/pdf_parser/cli.py` | `tests/test_cli.py` |
| 环境变量、地址、超时、重试、并发和代理 | `src/pdf_parser/config.py` | 配置或客户端测试 |
| `/health`、PDF/图像请求体、重试和响应协议 | `src/pdf_parser/clients/paddlex.py` | `tests/test_client.py`、`tests/test_image_input.py` |
| PDF 再校验和逐页拆分 | `src/pdf_parser/ingestion/pdf.py` | `tests/test_ingestion.py` |
| 图像签名识别 | `src/pdf_parser/ingestion/image.py` | `tests/test_image_input.py` |
| PDF 计数/批次与图像单页编排、失败策略和页序 | `src/pdf_parser/service.py` | `tests/test_service.py`、`tests/test_image_input.py` |
| 标签、阅读顺序和分阶段 OCR/Markdown 回退 | `src/pdf_parser/normalization/paddlex.py` | `tests/test_normalization.py` |
| 印章逐项绑定、坐标、编号和引用 | `src/pdf_parser/normalization/seal.py` | `tests/test_normalization.py` |
| 跨页表格候选检测 | `src/pdf_parser/cross_page_tables.py` | `tests/test_cross_page_tables.py` |
| 最终 JSON 类型和字段 | `src/pdf_parser/models.py` | 归一化、服务和 harness 验证测试 |
| 用户可见领域异常 | `src/pdf_parser/errors.py` | 最接近异常来源的测试 |
| PaddleX Pipeline、vLLM、CUDA/Ascend 设备与推理镜像配置 | `paddleocr-server/` | 推理模块静态检查与目标硬件验证 |
| 网关与推理模块的共同生命周期 | `compose.yaml`、`compose.ascend.yaml`、`scripts/docker.sh` | `tests/test_container_config.py` |

稳定行为只在 [`invariants.md`](invariants.md) 定义。具体远端配置不是架构事实，见 [`../operations/remote-state.md`](../operations/remote-state.md)。

## CUDA 多 Pipeline 部署

T4 当前验证方案由根 Compose 的 CUDA overlay 提供：Nginx 替代内部
`paddleocr-vl-api` 服务入口，`pipeline-1` 至 `pipeline-4` 启动 4 个独立 Pipeline，
共享单一 vLLM 服务。T4 实测将 4 个 Pipeline 放在 GPU 1，vLLM 配为 TP=1、DP=4，
使用 GPU 2/3/4/5。网关仍按单页调用 Pipeline，HTTP 边界、文档 fail-fast 和模块职责
不变。具体部署命令、参数、吞吐和超时结论见 [README 的 T4 配置说明](../../README.md)
与[基准报告](../reports/benchmarks/2026-11-13-t4-pipeline-replicas.md)。

这是 CUDA 显式选择的运行模式，不改变默认单 Pipeline Compose，也不适用于 Ascend。
2026-11-13 的全量对照显示吞吐提升约 81.3%，但 4 worker 新增 4 个超时页；因此记录为
当前可复用配置，稳定性推广门槛尚未通过。T4 的易变运行状态见
[`remote-state.md`](../operations/remote-state.md)。

### 双卡共置（CUDA 可选）

`compose.colocated.yaml` 叠加在基础和 replicas 配置后，将 pipeline-1/2 分别映射到
`COLOCATED_GPU_1/2`，共享 vLLM 可见同两张卡、TP=1/DP=2。使用
`scripts/docker-two-gpu.sh` 代理到统一 `scripts/docker.sh` 生命周期入口，读取独立
`.env.two-gpu`；不改变原单worker、四worker或Ascend方案。物理共置不提供请求与rank的固定配对。
显存预算需要为Pipeline预留，V100仍须现场验收；配置步骤见
[双卡部署手册](../../deploy/two-gpu/README.md)。
