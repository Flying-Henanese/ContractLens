# Architecture Map

## 系统边界

本仓库是远端 PaddleX `PP-StructureV3` / `layout-parsing` Pipeline 的轻量客户端，不承载模型
推理。当前产品边界只允许 Pipeline 模式；除非用户明确扩展范围，不加入 VLM、多模态模型或
外部 LLM。

```text
本地 PDF
  -> ingestion/pdf.py：校验并拆成单页 PDF
  -> service.py：按 concurrency 有界分批编排
  -> clients/paddlex.py：POST /layout-parsing
  -> normalization/paddlex.py：页面、OCR、版面和表格归一化
  -> normalization/seal.py：印章区域、全局坐标和正文引用
  -> models.py：Pydantic 输出契约
  -> cli.py：进度、错误呈现和 JSON 交付边界
```

FastAPI 边界由 `api.py` 承担：外部 multipart 上传先写入请求级临时目录，再调用
`service.py`；文档路由同步等待结果，票据路由当前只保留类型校验和未实现响应。

## 模块职责

| 关注点 | 权威模块 | 对应离线测试 |
| --- | --- | --- |
| FastAPI 上传、同步路由、接口超时和 HTTP 错误 | `src/pdf_parser/api.py` | `tests/test_api.py` |
| CLI 参数、输出路径、终端消息 | `src/pdf_parser/cli.py` | `tests/test_cli.py` |
| 环境变量、默认地址、超时、重试、并发、代理 | `src/pdf_parser/config.py` | 配置或客户端测试 |
| `/health`、请求体、重试、响应协议 | `src/pdf_parser/clients/paddlex.py` | `tests/test_client.py` |
| PDF 校验和逐页拆分 | `src/pdf_parser/ingestion/pdf.py` | `tests/test_ingestion.py` |
| 页级批次、失败策略、顺序恢复 | `src/pdf_parser/service.py` | `tests/test_service.py` |
| 标签、阅读顺序、OCR/Markdown 回退 | `src/pdf_parser/normalization/paddlex.py` | `tests/test_normalization.py` |
| 印章绑定、坐标转换、编号和引用 | `src/pdf_parser/normalization/seal.py` | `tests/test_normalization.py` |
| 最终 JSON 类型和字段 | `src/pdf_parser/models.py` | 归一化/服务测试及 README |
| 用户可见领域异常 | `src/pdf_parser/errors.py` | 最接近异常来源的测试 |

不要把 HTTP、PDF、归一化和 CLI 逻辑重新混入同一模块。公共边界使用类型标注，结构化数据优先
使用 Pydantic 模型。

## 必须保持的系统不变量

1. PDF 在本地逐页拆分，页码从 1 开始；并发有界，结果按 `page_num` 排序。
2. 每页请求显式发送 `fileType=0`、`visualize=false` 和不含正文的页级 `logId`。
3. 任一页面失败则整份文档失败，不生成伪装成功的部分结果。
4. 不记录 PDF Base64、完整原始响应、Markdown 图片 Base64 或敏感正文。
5. 印章 OCR polygon 是裁剪图局部坐标，只有取得可靠 `crop_bbox` 后才能平移到页面坐标。
6. 印章结果先按原始顺序绑定区域，再按 `(y0, x0)` 排序编号；数量不一致时坐标留空。
7. `content_references.target_id` 使用稳定 `seal_id`，字符偏移必须精确切出 `[印章N]`。
8. 输出坐标统一为预处理后页面像素、左上角原点，所有坐标必须落在页面范围内。
9. 顶层兼容结构和每页必需字段不得无理由重命名或删除。
10. 根目录和 `resources/` 中的 PDF、图片、样例 JSON 是用户数据，不是可改写的测试夹具。

更完整的协议字段、印章坐标公式、输出结构和失败策略以 [`AGENTS.md`](../AGENTS.md) 为准。

## 远端与本地事实的分界

- 本地代码决定请求构造、拆页、重试策略、归一化和输出结构。
- PaddleX 服务决定启用的识别能力、模型参数和实际返回形状。
- 涉及远端行为时先运行 `uv run pdf-parser health`；需要时读取 `/openapi.json` 和一份去除
  Base64 后的真实响应证据。
- 远端当前状态不能硬编码成客户端事实，烟测数值只能作为回归基线。
