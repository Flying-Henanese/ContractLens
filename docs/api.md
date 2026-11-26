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

## 文档解析

三个同步 `POST` 入口均通过 `multipart/form-data` 的 `file` 字段接收 PDF 或
BMP、JPEG/JPG、PNG、TIFF、WEBP 图像，并返回同一 `ParseResponse`。
PDF 接受 `application/pdf` 或 `application/octet-stream`。图像要求扩展名与标准
Content-Type 匹配，通过签名校验后以单张图像请求 PaddleX。

| 路径 | PDF 提交方式 |
| --- | --- |
| `/api/v1/documents/parse` | 逐页提交。`PDF_PARSER_CONCURRENCY` 决定每批在途页数，默认 `1`。 |
| `/api/v1/documents/parse-whole` | 原始 PDF 字节整体提交，网关只校验 PDF 并统计页数。 |
| `/api/v1/documents/parse-split` | 按连续页均分成最多四段，并发提交。段间页数最多相差一页，少于四页时每页一段。 |

三个入口均按原文页号返回 `data.doc_recognize_result`。提交的整份 PDF 或某段缺页、请求失败时，
整份文档返回失败。文档解析等待和 PaddleX 客户端超时配置均为 600 秒。

不接收 DOC、DOCX 或其他 Office 文档；请先在业务侧转换为 PDF 或受支持图像。

PDF 调用示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/documents/parse" `
  -F "file=@input.pdf;type=application/pdf"
```

比较解析策略时，在同一个环境中保持 `file`、服务配置和压测并发一致，只替换 URL 的末段。
对照整份耗时、成功页数、失败率，以及正文、表格和印章结果。副本模式下，整份请求由一个
Pipeline worker 处理，四段请求分别由 Nginx 分流。实际落点以 Nginx 的 `upstream` 日志为准。
新入口每页的 `parse_time` 包含该页所属整份或分段的请求耗时。对比吞吐时使用调用端测得的
整份耗时。

T4 CUDA 副本代理的请求体上限为 `256m`。Base64 和 JSON 编码后，原始 PDF 或单段 PDF 的
可用大小略低于 192 MiB。代理的 `proxy_read_timeout` 为 120 秒，按两次上游读取之间的等待时间计算。
更新挂载的代理模板后，重启副本拓扑以重新生成 Nginx 配置。

PNG 调用示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8888/api/v1/documents/parse" `
  -F "file=@page.png;type=image/png"
```

## 票据识别

`POST /api/v1/receipts/recognize` 接收相同的 `file` 字段。该接口为预留入口，验证上传类型后
返回 HTTP 501，预留的处理超时配置为 120 秒。

交互式接口文档位于 `http://127.0.0.1:8888/docs`。
