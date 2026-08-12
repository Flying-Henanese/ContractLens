---
status: active
owner: Codex
created: 2026-07-28
updated: 2026-08-12
scope:
  - ingestion
  - client
  - service
  - cli
supersedes:
  - per-page-submission
  - bounded-page-concurrency
blocked_by: []
---
# 整份 PDF 远端提交

状态：active  
负责人：Codex  
创建日期：2026-07-28  
最后更新：2026-08-12 +08:00

## 目标与用户价值

客户端应将原始完整 PDF 一次提交给 PaddleX 的 `/layout-parsing`，再将服务返回的多页结果按
页面顺序归一化为现有兼容 JSON。移除本地逐页拆分、页级并发与页级请求的实现及其文档描述。
不改变最终 JSON 字段、印章坐标规则或 fail-fast 语义。

## 当前事实与约束

- 现有 `iter_pdf_pages()` 逐页生成 PDF，`service.py` 按 `Settings.concurrency` 分批调用
  `parse_pdf_page()`；`PaddleXClient` 要求每个响应只含一页。
- 2026-07-28 对 `http://192.168.0.67:8880` 的预热实测：同一份 10 页、3.95 MB PDF 一次提交
  用时 28.627 秒并返回 10 页；10 次串行单页请求用时 46.814 秒并返回 10 页。
- 用户明确决定以完整 PDF 一次提交为当前处理流程。远端页数上限属于部署能力，客户端将验证
  返回页数必须与本地 PDF 页数一致。
- 保持 `fileType=0`、`visualize=false`、禁记 Base64/正文、加密或空 PDF 的 `InvalidPdfError`，
  以及整份请求失败即失败的策略。
- 根目录与 `resources/` 是用户数据；真实烟测结果仅写入 `output/smoke/`。

## 实施阶段

- [ ] 阶段 1：将 PDF 读取、远端请求和服务编排改为整份文档路径，并保持输出页序与 fail-fast。
- [ ] 阶段 2：更新离线单元测试、CLI 和烟测脚本，覆盖多页整份请求及返回页数不一致。
- [ ] 阶段 3：同步 README、AGENTS.md 与 harness 架构文档，执行离线门槛和真实烟测。

## 具体改动

- `ingestion/pdf.py` 仅校验并读取原始 PDF 字节及页数，不再生成单页 PDF。
- `clients/paddlex.py` 发送一次文档级请求，返回全部 `layoutParsingResults`，并验证其数量。
- `service.py` 以本地页数校验远端响应，按枚举的页号归一化每个结果；删除并发批次路径。
- 删除不再适用的 `concurrency` 设置和 CLI 参数，并调整 smoke 脚本。
- 更新测试与永久文档，记录已验证的性能结论但不将特定远端状态硬编码成运行时行为。

## 验证与验收

- 运行受影响的 client、ingestion、service、CLI 测试；多页最小 PDF 只产生一次 HTTP 调用，并
  生成顺序正确的多页输出；返回页数不一致抛出 `PaddleXError`。
- 运行 `& .\.harness\scripts\check.ps1`。
- 对可用远端运行一页和多页真实烟测，结果写入 `output/smoke/`，并检查输出页数、内容及印章坐标。

## 进度记录

- 2026-07-28 10:00 — 已创建计划；已完成远端健康检查和同源 10 页 A/B 性能测试。下一步：检查受影响实现、测试和 CLI/烟测脚本。
- 2026-08-12 — Harness 对齐复核确认目标仍未落地：当前实现、测试、CLI 和烟测脚本仍使用
  逐页拆分、页级请求和 `concurrency`。本次只更新事实日期，不宣称有实施进度，也不代替用户
  取消该目标。

## 意外发现

- 暂无。

## 决策记录

- 决策：采用一次完整 PDF 请求，而不是保留可选的逐页模式。
  理由：用户明确指定目标流程，且对目标远端的预热基准中整份提交快约 39%。
  日期：2026-07-28。

## 恢复与回滚

中断后从本计划的实施阶段继续。若实现或验证失败，可仅撤销本任务编辑的源代码、测试、文档和
本计划；不修改 `resources/` 或根目录样本。真实烟测生成物只位于 `output/smoke/`。

## 结果总结

待验收后填写。
