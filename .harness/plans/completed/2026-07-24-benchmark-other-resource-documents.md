# 使用其他 resources 文档对比 8880 与 8888 耗时

状态：completed  
负责人：Codex  
创建日期：2026-07-24  
完成日期：2026-07-24

## 目标

从 `resources/` 中选择此前未测的代表性 PDF，以完全相同的单页输入分别调用 8880 PaddleOCR-VL 和 8888 PP-StructureV3，比较预热后的端到端耗时水平。

## 已完成

- [x] 盘点 46 份 PDF、54 页资源。
- [x] 从通用票据、通用印章、营业执照、通用表格各选择 3 份，共 12 份新样本。
- [x] 检查两套服务健康状态并分别预热。
- [x] 用相同单页 PDF 和请求参数完成 12 组独立对比。
- [x] 记录端到端耗时、版面块、Markdown 字符数和 8118 VLM 指标增量。
- [x] 对 8888 的 60 秒异常页复测并渲染目视检查。
- [x] 生成 JSON 明细和 Markdown 报告，验证不含 Base64。

## 结果

- 两端均 12/12 成功。
- 中位数：8880 6.684 秒，8888 3.720 秒；8880 约慢 1.80 倍。
- 8888 在 11/12 页更快。
- `商务技术服务分册-泰安_3.pdf` 是稳定例外：8880 两次约 14.8 秒，8888 两次约 60 秒。
- 剔除该异常页后的均值：8880 9.116 秒，8888 3.756 秒；8880 约慢 2.43 倍。
- 8880 单页耗时与 VLM 生成 token 数高度相关（Pearson 0.904），与区域请求数不相关（-0.102）。

## 验证

- `run_benchmark.py` 通过 Ruff 格式、Ruff 静态检查和 `py_compile`。
- `comparison.json` 可解析，包含 12 个样本且无错误。
- 两端响应均确认 `use_seal_recognition=true`。
- 输出不含 Base64，错误日志为空。
- 异常页复测结果稳定，并经渲染确认属于同页多表格、多印章、拼接扫描的复杂版面。

## 产物

- `output/smoke/benchmark-other-resource-documents/report.md`
- `output/smoke/benchmark-other-resource-documents/comparison.json`
- `output/smoke/benchmark-other-resource-documents/run_benchmark.py`

## 决策记录

- 固定比较每份文档第 1 页，以排除文档页数差异。
- 预热时间单独记录，不计入正式统计。
- 全部请求均为两套服务的独立调用，没有串联或兜底路由。
- 对稳定长尾同时报告原始均值、中位数和剔除该页后的均值，避免单一指标误导。
