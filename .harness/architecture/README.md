# Architecture

## 系统边界与当前数据流

本仓库不承载模型推理。文档 API 当前接受 PDF 或受支持图像；CLI 仍只接受 PDF。PDF 仍采用
逐页远端请求，整份 PDF 提交是 active plan 中尚未落地的目标状态。

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

稳定行为只在 [`invariants.md`](invariants.md) 定义。具体远端配置不是架构事实，见 [`../operations/remote-state.md`](../operations/remote-state.md)。
