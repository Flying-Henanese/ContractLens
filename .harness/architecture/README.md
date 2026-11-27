# Architecture

## 系统边界与当前数据流

根目录 `src/pdf_parser/` 是业务网关，`paddleocr-server/` 是独立维护推理运行时的配置模块。
两者各有 Python 依赖和运行职责，由根目录 Compose 作为一套服务管理。

`POST /api/v1/documents/parse` 同步解析 PDF 或受支持的图像。上传暂存和初步校验完成后，
路由以 `DOCUMENT_TIMEOUT_SECONDS` 为解析等待和 PaddleX 客户端超时配置，当前为 600 秒。
解析等待超时返回 HTTP 504。`PDF_PARSER_TIMEOUT_SECONDS` 配置独立 CLI 的默认单次请求超时
（默认 120 秒，可由 `--timeout` 覆盖）。`POST /api/v1/receipts/recognize` 校验扩展名和
Content-Type 后返回 HTTP 501，120 秒是预留配置。CLI 的 `parse` 命令处理 PDF。网关在
Compose 网络内通过 `http://paddleocr-vl-api:8080` 请求 PaddleX。

PDF 的 HTTP 提交粒度由路由决定。`/api/v1/documents/parse` 和 CLI 采用逐页请求，
`/api/v1/documents/parse-whole` 提交原始完整 PDF，`/api/v1/documents/parse-split` 将 PDF 划分为
最多四个连续非空分段并发提交。整份和分段请求校验远端页数，再按原文页号归一化和合并。

```text
外部调用方
  -> api（根目录网关；业务 API）
       -> paddleocr-vl-api（PaddleX Pipeline；Compose 内部 DNS）
            -> paddleocr-vlm-server（PaddleOCR-VL / vLLM）
```

`PDF_PARSER_PORT`、`API_PORT` 分别控制宿主机的业务网关和 PaddleX 端口，默认 `8888` 和
`8880`。CUDA 另发布 vLLM 诊断端口 `VLM_PORT`（默认 `8118`），Ascend 的 `8118` 只在
Compose 网络内使用。Pipeline 和 vLLM 容器将 `./paddleocr-server` 只读挂载到
`/opt/paddleocr-server`。副本模式的 Nginx 容器单独挂载代理配置模板。

```text
逐页入口的 PDF
  -> ingestion/pdf.py::count_pdf_pages：读取 PDF，校验输入并取得总页数
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

## Compose 拓扑

- 根 `compose.yaml` 读取 `.env` 中的 `CONTRACTLENS_PLATFORM`，默认选择昇腾四副本。
  `cuda` 加载 `compose.cuda.yaml` 的单 Pipeline 拓扑。网关等待 `paddleocr-vl-api` 健康，
  Pipeline 等待 vLLM 健康。两平台的
  [vLLM 启动路径和设备要求](../../paddleocr-server/.harness/context/runtime-and-config.md)各自维护。
- 昇腾在 `.env` 中通过 `CONTRACTLENS_PIPELINE_MODE=single` 选择单 Pipeline，或在
  `replicas` 模式通过 `CONTRACTLENS_PIPELINE_WORKERS=2` 或 `4` 选择副本数。Overlay 将
  `paddleocr-vl-api` 替换为 Nginx，Nginx 等待所有 Pipeline worker 健康，再为请求做
  `least_conn` 分发。各 worker 共享 Pipeline 设备配置与一个 vLLM 服务。网关沿用原服务名和协议。
- Ascend 的启动、设备映射、并发容量和真实解析仍需目标主机验证。见
  [推理验证清单](../../paddleocr-server/.harness/checklists/verification.md)。

正文回退、普通元素/印章坐标和印章绑定等稳定行为只在 [`invariants.md`](invariants.md)
定义，本页不复制规则细节。

## 模块职责

| 关注点 | 权威模块 | 对应离线测试 |
| --- | --- | --- |
| FastAPI 的 PDF/图像上传、同步解析、票据占位路由和 HTTP 错误 | `src/pdf_parser/api.py` | `tests/test_api.py`、`tests/test_api_timeout.py`、`tests/test_image_input.py` |
| CLI 参数、输出路径、终端消息 | `src/pdf_parser/cli.py` | `tests/test_cli.py` |
| 环境变量、地址、超时、重试、并发和代理 | `src/pdf_parser/config.py` | 配置或客户端测试 |
| `/health`、PDF/图像请求体、重试和响应协议 | `src/pdf_parser/clients/paddlex.py` | `tests/test_client.py`、`tests/test_image_input.py` |
| PDF 校验、整份读取和按页分段 | `src/pdf_parser/ingestion/pdf.py` | `tests/test_ingestion.py`、`tests/test_multipage_api.py` |
| 图像签名识别 | `src/pdf_parser/ingestion/image.py` | `tests/test_image_input.py` |
| PDF 逐页、整份、分段编排，图像单页编排和失败策略 | `src/pdf_parser/service.py` | `tests/test_service.py`、`tests/test_multipage_api.py`、`tests/test_image_input.py` |
| 标签、阅读顺序和分阶段 OCR/Markdown 回退 | `src/pdf_parser/normalization/paddlex.py` | `tests/test_normalization.py` |
| 印章逐项绑定、坐标、编号和引用 | `src/pdf_parser/normalization/seal.py` | `tests/test_normalization.py` |
| 跨页表格候选检测 | `src/pdf_parser/cross_page_tables.py` | `tests/test_cross_page_tables.py` |
| 最终 JSON 类型和字段 | `src/pdf_parser/models.py` | 归一化、服务和 harness 验证测试 |
| 用户可见领域异常 | `src/pdf_parser/errors.py` | 最接近异常来源的测试 |
| PaddleX Pipeline、vLLM、CUDA/Ascend 设备与推理镜像配置 | `paddleocr-server/` | 推理模块静态检查与目标硬件验证 |
| 网关与推理模块的共同生命周期 | 根目录 `compose*.yaml`、`scripts/docker.sh` | `tests/test_container_config.py`、`tests/test_ascend_replicas.py` |

稳定行为只在 [`invariants.md`](invariants.md) 定义。具体远端配置不是架构事实，见 [`../operations/remote-state.md`](../operations/remote-state.md)。
