# Architecture

## 系统边界与当前数据流

本仓库不承载模型推理。当前实现仍采用逐页远端请求；整份 PDF 提交是 active plan 中尚未落地的目标状态。

```text
本地 PDF
  -> ingestion/pdf.py：校验并拆成带 1-based 页码的单页 PDF
  -> service.py：按 Settings.concurrency 有界分批
  -> clients/paddlex.py：每页 POST /layout-parsing，要求恰好返回一页
  -> normalization/paddlex.py：页面、OCR、版面、表格归一化
  -> normalization/seal.py：印章绑定、全局坐标和正文引用
  -> service.py：恢复 page_num 顺序并组装 ParseResponse
  -> cli.py / api.py：文件或 HTTP 交付边界
```

跨页表格候选检测是对已生成结果 JSON 的独立只读分析，不在上述主解析链路中。

## 模块职责

| 关注点 | 权威模块 | 对应离线测试 |
| --- | --- | --- |
| FastAPI 上传、同步路由、超时和 HTTP 错误 | `src/pdf_parser/api.py` | `tests/test_api.py`、`tests/test_api_timeout.py` |
| CLI 参数、输出路径、终端消息 | `src/pdf_parser/cli.py` | `tests/test_cli.py` |
| 环境变量、地址、超时、重试、并发和代理 | `src/pdf_parser/config.py` | 配置或客户端测试 |
| `/health`、页级请求体、重试和响应协议 | `src/pdf_parser/clients/paddlex.py` | `tests/test_client.py` |
| PDF 校验和逐页拆分 | `src/pdf_parser/ingestion/pdf.py` | `tests/test_ingestion.py` |
| 有界页级批次、失败策略和页序恢复 | `src/pdf_parser/service.py` | `tests/test_service.py` |
| 标签、阅读顺序、OCR/Markdown 回退 | `src/pdf_parser/normalization/paddlex.py` | `tests/test_normalization.py` |
| 印章绑定、坐标、编号和引用 | `src/pdf_parser/normalization/seal.py` | `tests/test_normalization.py` |
| 跨页表格候选检测 | `src/pdf_parser/cross_page_tables.py` | `tests/test_cross_page_tables.py` |
| 最终 JSON 类型和字段 | `src/pdf_parser/models.py` | 归一化、服务和 harness 验证测试 |
| 用户可见领域异常 | `src/pdf_parser/errors.py` | 最接近异常来源的测试 |

稳定行为只在 [`invariants.md`](invariants.md) 定义。具体远端配置不是架构事实，见 [`../operations/remote-state.md`](../operations/remote-state.md)。
