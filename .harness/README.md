# Agent Harness

本目录是 PDF Parser 的仓库内智能体导航、知识和可执行反馈层。根 [`AGENTS.md`](../AGENTS.md) 是自动加载的高层约束入口；这里按事实类型分层，避免同一规则在多个文件中重复维护。

## 按任务读取

| 任务 | 必读内容 | 执行入口 |
| --- | --- | --- |
| 定位模块或理解数据流 | [`architecture/README.md`](architecture/README.md) | `rg`、相关测试 |
| 修改稳定跨模块行为 | 架构说明及 [`architecture/invariants.md`](architecture/invariants.md) | `scripts/check.ps1` |
| 实现、修复或重构 | [`workflows/change.md`](workflows/change.md) | `scripts/check.ps1` |
| 代码评审 | [`workflows/review.md`](workflows/review.md) | 定向测试、`git diff` |
| 远端协议或模型行为 | [`workflows/remote-validation.md`](workflows/remote-validation.md) 和 [`operations/remote-state.md`](operations/remote-state.md) | `scripts/smoke.ps1` |
| 部署到 T4 并验证 | [`workflows/remote-deploy-and-smoke.md`](workflows/remote-deploy-and-smoke.md) 和 [`operations/remote-targets.md`](operations/remote-targets.md) | SSH、`scripts/smoke.ps1` |
| 跨模块或多阶段任务 | [`plans/CONVENTIONS.md`](plans/CONVENTIONS.md) | `plans/active/` |
| 查找历史决策或实验 | `plans/archive/`、`reports/` | 只读历史证据 |

除根 `AGENTS.md` 外，不要求每次任务读取全部 harness。按任务路由渐进加载即可。

## 权威边界

| 信息类型 | 唯一权威位置 |
| --- | --- |
| 智能体高层约束、产品禁区、数据安全 | [`AGENTS.md`](../AGENTS.md) |
| 当前模块边界和数据流 | [`architecture/README.md`](architecture/README.md) |
| 稳定跨模块不变量 | [`architecture/invariants.md`](architecture/invariants.md) |
| 实施、评审和远端验证方法 | [`workflows/`](workflows/) |
| 会过期的远端观测和烟测基准 | [`operations/`](operations/) |
| 进行中的目标状态和决策 | [`plans/active/`](plans/active/) |
| 已完成的实施历史 | [`plans/archive/`](plans/archive/) |
| 性能基准和专项调研 | [`reports/`](reports/) |
| 可重复机械反馈 | [`scripts/`](scripts/) |

代码、测试和文档不一致时，不凭文档猜测。先用实现、测试和实际协议证据确认，再修正对应的唯一权威文件。Active plan 可以描述尚未落地的目标状态，但必须明确当前事实和拟替代的不变量。

## 最短反馈回路

```powershell
& .\.harness\scripts\bootstrap.ps1
uv run python .harness\scripts\harness_lint.py
& .\.harness\scripts\check.ps1
& .\.harness\scripts\smoke.ps1 -InputPdf "resources\...\sample.pdf"
```

离线测试不得访问真实 PaddleX。真实烟测生成物只允许写入 `output/smoke/`。
