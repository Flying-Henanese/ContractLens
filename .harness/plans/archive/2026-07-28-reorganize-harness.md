---
status: completed
owner: Codex
created: 2026-07-28
updated: 2026-07-28
scope:
  - harness
  - project-instructions
  - validation
supersedes: []
blocked_by: []
---

# 重新组织智能体 Harness

## 目标与用户价值

将 harness 调整为“约束、架构、工作流、运行事实、历史报告”分层组织，消除多处重复维护的
权威规则，并为计划元数据和输出验证器增加可执行自检。此次工作不改变 PDF Parser 产品行为、
远端请求或输出字段。

## 当前事实与约束

- 根 `AGENTS.md` 同时包含智能体约束、架构、远端状态、烟测基准和路线图，内容过重。
- `.harness/ARCHITECTURE.md`、`WORKFLOW.md` 与 `AGENTS.md` 重复维护部分不变量。
- `plans/completed/` 混合保存代码实施计划、基准测试和调研报告。
- `validate_result.py` 手写输出结构，但尚未复用生产 Pydantic 模型，也没有独立测试。
- 必须保留现有 active 计划和所有历史记录，不修改用户样本或生产逻辑。

## 实施阶段

- [x] 阶段 1：建立分层目录和唯一权威边界，精简 `AGENTS.md`。
- [x] 阶段 2：分离实施计划、运行事实、基准与调研报告。
- [x] 阶段 3：增加计划自检，改造结果验证器并补测试。
- [x] 阶段 4：运行完整离线门槛，归档本计划。

## 验证与验收

- `uv run python .harness/scripts/harness_lint.py`
- `uv run pytest tests/test_harness.py --basetemp .pytest-tmp-harness`
- `& .\.harness\scripts\check.ps1`
- 文档内部链接、active 计划元数据和归档状态均通过自检。

## 进度记录

- 2026-07-28 — 完成现状审查并创建迁移计划.
- 2026-07-28 — 完成目录分层、历史迁移、验证器复用生产模型和 harness 自检.
- 2026-07-28 — 新增 5 个 harness 测试；完整门槛通过，30 个测试通过。

## 意外发现

暂无。

## 决策记录

- 决策：采用渐进式重组并保留全部历史文件。
  理由：避免在改善导航时丢失已有决策和实验上下文。
  日期：2026-07-28。

## 恢复与回滚

中断后以本计划的阶段清单和 `git diff` 为准继续。所有变更限于 `AGENTS.md`、`.harness/`
和 harness 测试，可按文件恢复，不涉及用户样本或远端状态写入。

## 结果总结

已建立按任务渐进加载的权威文档层，分离运行观测、实施归档和实验报告；新增计划/链接自检，并让结果验证器复用生产 Pydantic 模型。

验证：`uv run python .harness/scripts/harness_lint.py`、`uv run pytest tests/test_harness.py` 和 `.harness/scripts/check.ps1` 全部通过；完整测试为 30 passed、1 个第三方弃用警告。
