# PaddleOCR-VL 文档解析接口

服务基地址为 `http://192.168.0.194:8080`，需在可访问 `a100` 的内网环境中调用。两个解析接口均接收 JSON（`Content-Type: application/json`）并返回 JSON。

| 方法 | 地址 | 用途 |
| --- | --- | --- |
| POST | `http://192.168.0.194:8080/layout-parsing` | 解析 PDF 或图片，返回逐页结果。 |
| POST | `http://192.168.0.194:8080/restructure-pages` | 将逐页结果合并成一份 Markdown。 |
| GET | `http://192.168.0.194:8080/health` | 检查服务健康状态。 |
| GET | `http://192.168.0.194:8080/openapi.json` | 查看完整接口定义。 |

## 解析 PDF 或图片

### 入参

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file` | string，必填 | 文件原始字节的 Base64 字符串，或服务端可访问的文件 URL。Base64 直接传编码内容。 |
| `fileType` | integer | PDF 传 `0`，图片传 `1`。使用 Base64 时显式填写。 |
| `visualize` | boolean，可选 | 设为 `false` 可关闭额外的可视化图和中间图。 |

PDF 请求示例。整份 PDF 和单页 PDF 使用相同格式。

```json
{
  "file": "<PDF 文件的 Base64>",
  "fileType": 0,
  "visualize": false
}
```

- **整份 PDF**：在 `file` 中提交完整文件。响应按页返回，顺序与原文档一致。
- **指定 PDF 页**：先从原 PDF 抽出目标页，将抽出的单页 PDF 提交。接口没有页码参数。
- **单页图片**：在 `file` 中提交 PNG 或 JPEG 的 Base64，并将 `fileType` 设为 `1`。

### 出参

成功时返回 HTTP 200，`errorCode` 为 `0`。主要字段如下。

| 字段 | 说明 |
| --- | --- |
| `logId` | 本次请求的标识，用于定位服务日志。 |
| `result.dataInfo` | 输入文件信息。PDF 的 `numPages` 可用于与结果数量核对。 |
| `result.layoutParsingResults` | 逐页结果数组。单页输入取第 0 项。 |
| `layoutParsingResults[i].prunedResult` | 该页的结构化解析结果。合并时原样传给下一接口。 |
| `layoutParsingResults[i].markdown.text` | 该页的 Markdown 正文。 |
| `layoutParsingResults[i].markdown.images` | Markdown 引用的图片。键是相对于 `.md` 文件的路径，值是图片的 Base64。 |

单页响应示例（`prunedResult` 的内容从略）。

```json
{
  "logId": "<请求标识>",
  "errorCode": 0,
  "errorMsg": "Success",
  "result": {
    "dataInfo": { "numPages": 1 },
    "layoutParsingResults": [
      {
        "prunedResult": {},
        "markdown": {
          "text": "# 示例标题",
          "images": {}
        }
      }
    ]
  }
}
```

单页解析完成后，将 `markdown.text` 以 UTF-8 保存为 `.md`。如有 `markdown.images`，将图片解码后按返回的相对路径与 `.md` 一起保存。

## 将多页结果合并为一份 Markdown

### 入参

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `pages` | array，必填 | 按原 PDF 页序传入每页结果。 |
| `pages[i].prunedResult` | object，必填 | 原样复制解析响应中该页的 `prunedResult`。 |
| `pages[i].markdownImages` | object 或 null，可选 | 复制解析响应中该页的 `markdown.images`。无图时可传 `null`。 |
| `concatenatePages` | boolean | 设为 `true`，将所有页拼成一份文档。 |
| `mergeTables` | boolean，可选 | 设为 `true` 时尝试合并跨页表格。 |
| `relevelTitles` | boolean，可选 | 设为 `true` 时重建标题层级。 |

将下面两处空对象分别替换成前两页的完整 `prunedResult`。有更多页时继续按页序加入 `pages`。

```json
{
  "pages": [
    { "prunedResult": {}, "markdownImages": null },
    { "prunedResult": {}, "markdownImages": null }
  ],
  "concatenatePages": true
}
```

### 出参

成功时返回 HTTP 200，`errorCode` 为 `0`。当 `concatenatePages` 为 `true` 时，`result.layoutParsingResults` 返回一项。读取 `result.layoutParsingResults[0].markdown.text` 作为整份文档的正文，并使用同一项的 `markdown.images` 保存引用图片。最终的 `.md` 文件由调用方保存。

接口调用失败时，记录 HTTP 状态码，以及响应中可用的 `errorCode`、`errorMsg` 和 `logId`。

[PaddleOCR v3.6 服务调用文档](https://www.paddleocr.ai/v3.6.0/en/version3.x/pipeline_usage/PaddleOCR-VL.html#43-client-side-invocation)
