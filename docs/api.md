# HTTP API

启动可接受外部请求的 FastAPI 服务：

```powershell
uv run pdf-parser-api
```

默认监听 `0.0.0.0:8888`，也可通过 Python 模块或 Uvicorn 启动：

```powershell
uv run python -m pdf_parser.main
uv run uvicorn pdf_parser.main:app --host 0.0.0.0 --port 8888
```

服务提供两个同步接口（客户端需等待接口完成）：

- `POST /api/v1/documents/parse`：上传 PDF 或 BMP、JPEG/JPG、PNG、TIFF、WEBP 图像，字段名为 `file`。PDF 的 Content-Type 可为 `application/pdf` 或 `application/octet-stream`；图像的文件扩展名必须与其标准 Content-Type 匹配。图像会在本地校验二进制格式后，以单页文档形式调用 PaddleX，整体及远端单次请求超时均为 300 秒。
- `POST /api/v1/receipts/recognize`：上传 PDF 或上述图像格式，字段名为 `file`，超时配置为 120 秒。该接口目前仅预留，固定返回 HTTP 501。

不接收 DOC、DOCX 或其他 Office 文档；请先在业务侧转换为 PDF 或受支持图像。

PDF 调用示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/documents/parse" `
  -F "file=@input.pdf;type=application/pdf"
```

PNG 调用示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/documents/parse" `
  -F "file=@page.png;type=image/png"
```

交互式接口文档位于 `http://127.0.0.1:8888/docs`。