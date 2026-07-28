# Execution Plan Conventions

执行计划是复杂任务的可恢复工作记录。它描述正在推进的目标状态，不替代当前代码、测试或稳定架构文档。

## 生命周期

1. 在 `active/` 新建 `YYYY-MM-DD-short-topic.md`。
2. 实施中持续更新进度、发现、决策和验证证据。
3. 完成、取消或明确终止时写结果总结，将状态改为 `completed` 或 `cancelled`。
4. 将文件移动到 `archive/`；稳定结论回写代码、测试或对应权威文档。
5. 性能基准和专项调研分别进入 `reports/benchmarks/`、`reports/investigations/`。

## 必需元数据

新计划使用以下 YAML front matter：

```yaml
---
status: active
owner: Codex
created: YYYY-MM-DD
updated: YYYY-MM-DD
scope:
  - module-name
supersedes:
  - invariant-or-document
blocked_by: []
---
```

Active plan 的 `status` 必须为 `active`，日期必须与文件名前缀一致。若目标状态与当前稳定规则不同，应在 `supersedes` 和正文中明确指出拟替代内容，避免把计划误读为已落地事实。

## 正文要求

计划至少包含：目标与用户价值、当前事实与约束、实施阶段、验证与验收、进度记录、意外发现、决策记录、恢复与回滚、结果总结。阶段必须面向可观察结果；命令记录实际结果，不依赖聊天或终端历史。

运行 `uv run python .harness/scripts/harness_lint.py` 检查 active 计划元数据、索引和本地文档链接。
