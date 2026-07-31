# PDF Parser

HTTP 文档解析接口支持 PDF 以及 BMP、JPEG/JPG、PNG、TIFF、WEBP 图像；DOC/DOCX 需先转换。详细调用方式见 [docs/api.md](docs/api.md)。

FastAPI 服务的启动方式、接口路径和调用示例见 [`docs/api.md`](docs/api.md)。

一个以远端 PaddleX `layout-parsing` Pipeline 为主链路的 PDF 文档解析工具；可选启用印章级 VLM 兜底。

## 已实现

- 将 PDF 逐页拆分后调用 PaddleX，避免服务默认最多处理 10 页造成文档截断。
- 支持请求超时、网络失败重试和受控并发。
- 将 PaddleX `prunedResult` 转换为与现有样例相近的 JSON。
- 输出正文、版面类型、边界框、阅读顺序、OCR/印章文本和处理耗时。
- 保留表格 HTML，并将每枚物理印章结构化为可定位的独立元素。
- 提供独立的 JSON 后处理模块，用于识别可能延续到下一页的表格。
- 可选对已检测但 OCR 文字缺失或低置信度的印章执行 VLM 双视图复核。

## 安装

```powershell
uv sync
```

默认 PaddleX 服务地址为 `http://192.168.0.67:8880`；印章 VLM 兜底默认关闭。

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

也支持 `.env` 文件或环境变量。可以先复制模板，再按实际远端
PaddleOCR-VL / PaddleX 服务地址修改 `PDF_PARSER_ENDPOINT`：

```powershell
Copy-Item .env.template .env
```

也可以在当前 PowerShell 会话中直接设置：

```powershell
$env:PDF_PARSER_ENDPOINT = "http://192.168.0.67:8880"
$env:PDF_PARSER_TIMEOUT_SECONDS = "180"
$env:PDF_PARSER_USE_LAYOUT_DETECTION = "true"
$env:PDF_PARSER_LAYOUT_THRESHOLD = "0.5"
# 如确实需要让请求继承系统 HTTP(S) 代理：
$env:PDF_PARSER_TRUST_ENV = "true"
```

印章 VLM 兜底通过环境变量启用。它只处理 PaddleX 已检测到，但印章 OCR 文字为空、缺少分数或分数低于阈值的元素；未检测到的印章不做整页复查。原始裁剪图与红色隔离视图必须得到一致的完整文字才会采用，否则保留 PaddleX 结果：

```powershell
$env:PDF_PARSER_VLM_ENABLED = "true"
$env:PDF_PARSER_VLM_ENDPOINT = "http://192.168.0.194:8000"
$env:PDF_PARSER_VLM_MODEL = "qwen3.6-27b"
$env:PDF_PARSER_VLM_TIMEOUT_SECONDS = "30"
$env:PDF_PARSER_VLM_MAX_ATTEMPTS = "5"
$env:PDF_PARSER_VLM_SEAL_OCR_THRESHOLD = "0.9"
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
