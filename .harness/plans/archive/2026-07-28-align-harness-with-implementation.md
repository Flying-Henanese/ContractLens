---
status: completed
owner: Codex
created: 2026-07-28
updated: 2026-07-28
scope:
  - client
  - normalization
  - harness-architecture
  - tests
supersedes: []
blocked_by: []
---

# 对齐 Harness 不变量与当前实现

## 目标与用户价值

修复 Harness 审查发现的四处偏差：协议解码错误缺少页码、跨页表格职责命名错误、当前数据流缺少逐页拆分与有界批次，以及多印章显式裁剪框未逐项优先使用。完成后，架构文档、稳定不变量、实现和回归测试应表达同一行为。

## 当前事实与约束

- `PaddleXClient._decode_response()` 当前无法知道页码。
- `cross_page_tables.py` 只报告候选，不修改或合并表格。
- 当前实现仍使用 `iter_pdf_pages()`、有界批次和单页远端请求。
- `_resolve_seal_regions()` 只有在所有结果都有显式框时才采用显式框。
- 不改变当前逐页提交策略；整份 PDF 提交仍由另一 active plan 管理。

## 实施阶段

- [x] 阶段 1：为页级响应解码错误加入页码上下文并补客户端测试。
- [x] 阶段 2：逐印章应用裁剪框优先级并补多印章测试。
- [x] 阶段 3：修正架构数据流和跨页模块职责描述。
- [x] 阶段 4：运行定向与完整离线验证并归档计划。

## 验证与验收

- `uv run pytest tests/test_client.py tests/test_normalization.py --basetemp .pytest-tmp-alignment`
- `& .\.harness\scripts\check.ps1`
- 非 JSON 和非对象页级响应错误包含页码。
- 部分印章带显式 `crop_bbox` 时，该印章仍优先使用显式框。
- Harness 架构图明确当前逐页路径，跨页表格职责称为候选检测。

## 进度记录

- 2026-07-28 — 创建计划并确认四处偏差。
- 2026-07-28 — 客户端响应形状错误加入页码上下文；印章裁剪框改为逐项优先。
- 2026-07-28 — 架构图和模块职责完成对齐；定向测试 11 passed，完整测试 33 passed。

## 意外发现

暂无。

## 决策记录

- 决策：修复实现以兑现逐印章裁剪框优先级，而不是弱化不变量。
  理由：显式服务端字段是最可靠的坐标来源，不应因同页其他印章缺失该字段而被丢弃。
  日期：2026-07-28。

## 恢复与回滚

中断后从未完成阶段继续；改动仅涉及客户端、印章归一化、对应测试和架构文档，不触碰样本、远端配置或输出字段。

## 结果总结

四处偏差均已修复：当前逐页数据流和跨页候选检测职责已准确记录；页级非 JSON/非对象响应错误包含页码；多印章可逐项优先采用显式裁剪框。

验证：定向测试 11 passed；Harness 完整门槛 33 passed、1 个第三方弃用警告；git diff --check 通过。
