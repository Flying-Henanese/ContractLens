# HTTP API

启动可接受外部请求的 FastAPI 服务：

```powershell
uv run pdf-parser-api
```

该入口默认监听 `0.0.0.0:8888`。也可以通过 Python 模块或 Uvicorn 启动：

```powershell
uv run python -m pdf_parser.main
uv run uvicorn pdf_parser.main:app --host 0.0.0.0 --port 8888
```

服务提供两个同步请求接口（客户端需要等待接口返回）：

- `POST /api/v1/documents/parse`：上传 PDF 文档，字段名为 `file`。复用现有文档解析
  Pipeline，整体请求及 PaddleX 单页请求超时均为 300 秒。
- `POST /api/v1/receipts/recognize`：上传票据 PDF 或常见图片，字段名为 `file`，超时配置
  为 120 秒。当前仅预留接口，固定返回 HTTP 501，识别逻辑将在后续补充。

文档解析示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/documents/parse" `
  -F "file=@input.pdf;type=application/pdf"
```

票据接口示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/receipts/recognize" `
  -F "file=@receipt.jpg;type=image/jpeg"
```

交互式接口文档位于 `http://127.0.0.1:8888/docs`。
