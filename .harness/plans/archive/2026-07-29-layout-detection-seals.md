---
status: completed
owner: Codex
created: 2026-07-29
updated: 2026-07-29
scope:
  - config
  - client
  - normalization
  - output-contract
supersedes:
  - seal-detail-requires-seal-res-list
blocked_by: []
---
# 无 seal_res_list 的印章结构化

## 目标与用户价值

显式启用 PaddleOCR-VL 版面检测，并在 `seal_res_list` 缺失时使用
`layout_det_res.boxes[label=seal]` 构造契约完整、可定位且可引用的 `SealDetail`。

## 当前事实与约束

- 当前客户端未发送 `useLayoutDetection` 或 `layoutThreshold`。
- 当前归一化只有 `seal_res_list` 存在时才创建 `SealDetail`；否则普通版面块可能输出
  `DocumentDetail(type="Seal")`。
- 2026-07-29 对 `http://192.168.0.67:8880/layout-parsing` 的真实测试显示：单页 PDF
  显式使用 `useLayoutDetection=true`、`layoutThreshold=0.5` 后返回一个 seal 框，
  `score=0.9355565309524536`、`coordinate=[592,0,861,222]`，但没有 `seal_res_list`。
- `layoutThreshold=0.5` 是可配置默认值，不宣称是所有文档的最优阈值。

## 实施阶段

- [x] 增加请求参数和配置测试。
- [x] 让区域检测独立于印章 OCR 结果生成 `SealDetail`，并禁止不完整的普通 Seal。
- [x] 更新环境模板、README、架构不变量和远端观测。
- [x] 运行离线检查和真实 PDF 烟测。

## 验证与验收

- 请求包含 `useLayoutDetection=true` 和配置的 `layoutThreshold`。
- 无 `seal_res_list`、但有 seal 版面框时生成带 score、坐标、ID、token 和引用的
  `SealDetail`，`texts=[]`。
- `ParseResponse` 拒绝 `DocumentDetail(type="Seal")`。
- 完整 harness 检查通过；真实烟测结果通过 `validate_result.py`。

## 进度记录

- 2026-07-29 — 完成远端 A/B 探测并建立计划。
- 2026-07-29 — 请求配置、区域型 SealDetail、模型守卫、离线测试和文档已完成；下一步执行完整检查与真实烟测。
- 2026-07-29 — 完整检查 38 项测试通过；真实单页 PDF 烟测及严格输出契约校验通过。

## 意外发现

- 暂无。

## 决策记录

- 决策：阈值默认 0.5 且可通过 `PDF_PARSER_LAYOUT_THRESHOLD` 调整。
  理由：与官方默认和已验证请求一致，同时避免把单一样本结果当成永久最优值。

## 恢复与回滚

中断后从未完成阶段继续；回滚仅限本任务源代码、测试、文档和计划文件。

## 结果总结

已显式发送版面检测参数；无 `seal_res_list` 时由版面框生成完整 `SealDetail`。完整离线检查和 `.67:8880` 真实 PDF 烟测通过。
