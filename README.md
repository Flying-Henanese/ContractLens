# PDF Parser

HTTP 文档解析接口支持 PDF 以及 BMP、JPEG/JPG、PNG、TIFF、WEBP 图像；DOC/DOCX 需先转换。详细调用方式见 [docs/api.md](docs/api.md)。

FastAPI 服务的启动方式、接口路径和调用示例见 [`docs/api.md`](docs/api.md)。

一个基于 PaddleX `layout-parsing` Pipeline 的 PDF 文档解析工具。根目录的统一 Docker
Compose 同时编排本项目的 FastAPI 网关、PaddleX Pipeline 和 PaddleOCR-VL/vLLM 推理进程；
网关仍只负责输入校验、远端调用和兼容 JSON 归一化，不在自身容器中执行模型推理。

## 已实现

- 将 PDF 逐页拆分后调用 PaddleX，避免服务默认最多处理 10 页造成文档截断。
- 支持请求超时、网络失败重试和受控并发。
- 将 PaddleX `prunedResult` 转换为与现有样例相近的 JSON。
- 输出正文、版面类型、边界框、阅读顺序、OCR/印章文本和处理耗时。
- 保留表格 HTML，并将每枚物理印章结构化为可定位的独立元素。
- 提供独立的 JSON 后处理模块，用于识别可能延续到下一页的表格。

## 安装

```powershell
uv sync
```

独立运行 CLI 或 FastAPI 时，需要通过 `PDF_PARSER_ENDPOINT` 配置可访问的 PaddleX 服务地址。

## 统一 Docker Compose 部署

`paddleocr-server/` 是已导入的 PaddleOCR-VL 推理模块，保留其 CUDA、Ascend、Pipeline 和
vLLM 配置。根目录 Compose 将下列三个进程作为同一个项目启动和停止：

```text
api                       对外文档接口，默认端口 8888
paddleocr-vl-api          PaddleX layout-parsing Pipeline，默认端口 8880
paddleocr-vlm-server      PaddleOCR-VL vLLM 后端，默认端口 8118（CUDA）
```

网关在 Compose 网络内固定通过 `http://paddleocr-vl-api:8080` 调用 Pipeline；这里的
`8080` 是 Pipeline 容器端口，不能替换为宿主机端口 `8880`。因此同一条命令会等待
vLLM、Pipeline 和网关按依赖顺序启动，`down` 也会停止整套栈。

复制环境模板后，请确认设备编号、模型缓存路径和镜像标签与目标服务器一致：

```bash
cp .env.template .env
bash scripts/docker.sh config
bash scripts/docker.sh up
bash scripts/docker.sh ps
```

默认是 CUDA Compose。Ascend 使用独立的完整 Compose 文件：

```bash
cp .env.ascend.template .env.ascend
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh up
```

本地没有 Docker、目标驱动、模型缓存或 GPU/NPU 时，不要尝试运行上述命令；可先运行离线
Python 测试和脚本语法检查，之后再在目标服务器完成 Compose 和真实解析烟测。

## 使用

检查服务：

```powershell
uv run pdf-parser health
```

解析 PDF：

```powershell
uv run pdf-parser parse "4-4通用表格\2大洋信息技术有限公司_商务_7.投标人信息表.pdf"
```

默认输出到当前工作目录的 `output/`，文件名为
`output/<原文件名>_result.json`。也可以指定输出位置：

```powershell
uv run pdf-parser parse input.pdf -o output\result.json
```

常用参数：

```text
--endpoint       PaddleX 服务地址
--timeout        单页超时秒数，默认 120
--retries        网络失败重试次数，默认 2
--concurrency    并行页数，默认 1
```

服务资源允许时可增加并发：

```powershell
uv run pdf-parser parse input.pdf --concurrency 2
```

独立运行时也支持 `.env` 文件或环境变量。可以先复制模板，再按实际远端
PaddleOCR-VL / PaddleX 服务地址修改 `PDF_PARSER_ENDPOINT`：

```powershell
Copy-Item .env.template .env
```

也可以在当前 PowerShell 会话中直接设置：

```powershell
$env:PDF_PARSER_ENDPOINT = "http://192.168.0.194:8080"
$env:PDF_PARSER_TIMEOUT_SECONDS = "180"
$env:PDF_PARSER_USE_LAYOUT_DETECTION = "true"
$env:PDF_PARSER_LAYOUT_THRESHOLD = "0.5"
# 如确实需要让请求继承系统 HTTP(S) 代理：
$env:PDF_PARSER_TRUST_ENV = "true"
```

CLI 参数优先于环境变量。默认不继承系统代理，避免内网 PaddleX 地址被错误发送到代理服务器。
客户端默认显式启用版面检测，并使用可配置的 `layoutThreshold=0.5`。该值与 PaddleOCR-VL
默认值及当前远端验证配置一致，是召回率与误检之间的中性起点，不代表所有文档的最优阈值。

## 输出结构

```json
{
  "code": "success",
  "message": "",
  "tips": null,
  "data": {
    "task_id": "",
    "file_url": "",
    "status": 4,
    "message": "",
    "doc_recognize_result": [
      {
        "page_num": 1,
        "document_content": "...",
        "image_width": 1191,
        "image_height": 1684,
        "document_details": [
          {
            "type": "Seal",
            "seal_id": "page-1-seal-1",
            "reference_token": "[印章1]",
            "seal_region_bbox": [620, 1, 850, 198],
            "texts": [
              {
                "text": "大洋信息技术有限公司",
                "ocr_confidence": 0.8227,
                "layout_bbox": [629, 1, 844, 182]
              }
            ]
          }
        ],
        "content_references": [
          {
            "token": "[印章1]",
            "target_type": "Seal",
            "target_id": "page-1-seal-1",
            "start_offset": 4,
            "end_offset": 9
          }
        ],
        "parse_time": 1.23
      }
    ],
    "aigc": {
      "Label": "AIGCLabelType.AI_GENERATED",
      "ProcessingTypes": ["ocr"]
    }
  }
}
```

`layout_fallback_text` ?? PaddleX `parsing_res_list[].block_content` ???? HTML ??????????????????? OCR ???????????????? `markdown.images` ? Base64 ?????

`image_width`、`image_height` 和 `layout_bbox` 统一使用 PaddleX 渲染后的页面像素坐标系。印章 OCR 的 `rec_polys` 原本是裁剪图局部坐标；客户端优先读取 `seal_res_list[].crop_bbox`，当前服务没有该字段时从 `markdown.images` 的印章裁剪图键取得实际整数裁剪框，最后才回退到 `layout_det_res`。转换后的整页 polygon 存入 `texts[].position`，外接矩形存入 `texts[].layout_bbox`。

每枚物理印章生成一个 `Seal` 元素；同一印章识别出的多段文字放在 `texts[]` 中。正文中的 `[印章N]` 通过 `content_references[].target_id` 对应到 `seal_id`。

## 跨页表格识别

解析完成后，可独立检查结果 JSON 中的跨页表格候选：

```powershell
uv run python -m pdf_parser.cross_page_tables output\result.json
```

当前规则将上一页空间位置最靠后的表格，与下一页顶部没有其他版面元素的表格进行比较；HTML
表格按 `colspan` 展开后的最大列数相同时，输出一个候选。检测结果只包含页码、元素下标、列数和
两个表格的 `layout_bbox`，不会修改或合并原始 JSON。

## 开发与测试

```powershell
uv run ruff check .
uv run pytest
```

## 当前限制

- 当前印章区域和 `seal_res_list` 数量不一致时，不猜测对应关系；保留印章文字，但不输出可能错误的页面坐标。
- 公式、图表识别依赖服务端启用相应模型。
- 当前采用失败即停止策略，不生成不完整的“成功”结果；断点续跑将在后续版本加入。
- 跨页表格目前只做候选识别，不合并表格 HTML 或正文。

### T4 CUDA：4 个 Pipeline worker + vLLM DP=4

T4 上已验证并正在运行的配置使用 Nginx 接收内部 Pipeline 请求，再将单页请求分发给
4 个独立 Pipeline worker；4 个 worker 共享一个 vLLM 服务，vLLM 使用 TP=1、DP=4。
这是一项显式选择的 CUDA 部署配置，要求 Docker Compose >= 2.24.4，不适用于 Ascend。
它保留单 Pipeline 默认部署，启用时不会改变网关 API、逐页处理或文档 fail-fast 行为。
性能结论和长尾限制见[基准报告](.harness/reports/benchmarks/2026-11-13-t4-pipeline-replicas.md)。

T4 的 `.env` 运行参数如下；GPU 编号是宿主机编号：

```dotenv
PIPELINE_GPU_ID=1
VLM_GPU_IDS=2,3,4,5
VLM_DATA_PARALLEL_SIZE=4
VLM_DATA_PARALLEL_BACKEND=mp
VLM_GPU_MEMORY_UTILIZATION=0.6
VLM_MAX_NUM_SEQS=16
VLM_MAX_NUM_BATCHED_TOKENS=16384
```

用以下命令选择四 worker 配置并检查健康状态。`PIPELINE_SUBGRAPH_CONCURRENCY=16`
设置每个 worker 的子图并发；4 个 worker 共用 Pipeline GPU 1。镜像、模型及 vLLM
参数保持与报告记录一致。

```bash
CONTRACTLENS_PLATFORM=cuda \
CONTRACTLENS_PIPELINE_MODE=replicas \
CONTRACTLENS_PIPELINE_WORKERS=4 \
PIPELINE_SUBGRAPH_CONCURRENCY=16 \
bash scripts/docker.sh config

CONTRACTLENS_PLATFORM=cuda \
CONTRACTLENS_PIPELINE_MODE=replicas \
CONTRACTLENS_PIPELINE_WORKERS=4 \
PIPELINE_SUBGRAPH_CONCURRENCY=16 \
bash scripts/docker.sh up
CONTRACTLENS_PLATFORM=cuda \
CONTRACTLENS_PIPELINE_MODE=replicas \
CONTRACTLENS_PIPELINE_WORKERS=4 \
bash scripts/docker.sh ps
```

Nginx 使用固定版本及 digest 的官方 Alpine 镜像，按 Docker DNS 动态解析 worker；代理不记录
正文，也不自动重发推理 POST。worker 保留 Pipeline 内部串行保护，实验配置关闭自动重启。
当前实测在整书负载下吞吐比单 worker 高约 81.3%，但 4 worker 出现 6 个超时，其中
4 页是单 worker 对照中成功的页面，因此当前记录为已验证的运行方案，尚未达到零新增超时的
推广门槛。该入口也尚未定义面向生产流量的过载拒绝策略。

性能测试：在已具备项目依赖的环境执行
`python scripts/benchmark_replicas.py --pdf tmp/pdfs/book.pdf --run A-1 --pages 1,2,3,4,5,6,7,8`。
使用 `--pages all` 验证整书；每页请求、唯一页号、质量验证、端到端延迟、DP Prometheus
指标及 GPU 利用率写入 `output/smoke/<run>/`，拆分页写入 `tmp/pdfs/`。
默认失败后停止提交新页，未提交页有明确终态；请求成功与严格质量门槛分别统计。
显式使用 `--continue-timeout-pages`（矩阵脚本设置 `BENCHMARK_CONTINUE_TIMEOUTS=1`）时，
仅在 vLLM 和 Pipeline 健康检查均通过后继续其他独立页面；仍记录超时，完整测试有失败时
客户端退出码为 1，未完成时为 2。网关文档级 fail-fast 不变，不生成伪成功的整书结果。

回滚：取消实验客户端后，从命令环境中移除 `CONTRACTLENS_PIPELINE_MODE`、
`CONTRACTLENS_PIPELINE_WORKERS`、`PIPELINE_SUBGRAPH_CONCURRENCY` 和 `PIPELINE_2_STATE`，
再运行 `bash scripts/docker.sh up`，由统一生命周期入口恢复原单 Pipeline 拓扑。

需要复测矩阵时，`scripts/run_replicas_benchmark.sh D <label>` 使用四副本、每副本子图并发
16、客户端并发 8；与双副本 C 比较会同时增加总供给上限（32 → 64），须单独报告。

### 双 GPU 共置部署（2 Pipeline + DP=2）

每卡一个 Pipeline worker 和一个 vLLM rank 的可选 CUDA 方案见
[运维部署手册](deploy/two-gpu/README.md)。使用独立 `.env.two-gpu` 和
`bash scripts/docker-two-gpu.sh`，可明确选择宿主两张 GPU；不改变原默认部署及 Ascend 配置。
T4验证不等于V100现场验收。
