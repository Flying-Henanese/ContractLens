# Agent Harness

本目录是 PDF Parser 的智能体编程 harness：它把项目知识、实施流程、执行计划和确定性反馈
放在仓库内，使 Codex 能够从任务描述一路完成定位、修改、验证和交付。

OpenAI 当前没有规定名为 `.harness` 的固定目录 schema。Codex 自动加载的仓库指令入口仍是
根目录 [`AGENTS.md`](../AGENTS.md)；本目录采用 OpenAI harness engineering 的原则组织：入口保持
可导航，详细知识按需披露，验证可机械执行，复杂工作留下可恢复的计划和决策记录。

## 阅读顺序

1. 始终先读 [`AGENTS.md`](../AGENTS.md)，它是约束的权威来源。
2. 用 [`ARCHITECTURE.md`](ARCHITECTURE.md) 定位数据流、模块边界和改动位置。
3. 用 [`WORKFLOW.md`](WORKFLOW.md) 选择实现、测试、评审和交付步骤。
4. 复杂任务按 [`PLANS.md`](PLANS.md) 创建并维护执行计划。
5. 用 `scripts/` 中的命令获得可重复的反馈，不用主观判断代替测试结果。

## 目录地图

```text
.harness/
├── README.md                    # 智能体入口和导航
├── ARCHITECTURE.md              # 数据流、模块职责和稳定边界
├── WORKFLOW.md                  # 端到端开发、验证和评审流程
├── PLANS.md                     # 执行计划规范与模板
├── plans/
│   ├── active/README.md         # 进行中的跨阶段任务
│   └── completed/README.md      # 已完成计划的归档约定
└── scripts/
    ├── bootstrap.ps1            # 创建/同步可工作的本地环境
    ├── check.ps1                # lint、格式和离线测试反馈
    ├── smoke.ps1                # 安全的真实 PDF 远端烟测
    └── validate_result.py       # 输出 JSON 契约与坐标不变量检查
```

## 权威性和维护规则

- 用户当前任务中的明确要求优先于仓库文档。
- `AGENTS.md` 定义产品边界、协议、输出和数据安全；本目录负责导航与执行方式。
- 代码、测试与文档不一致时，不猜测。先以可执行测试和实际协议证据确认，再同步修正文档。
- 新增稳定模块、命令或不变量时，同一改动中更新相应 harness 文档或脚本。
- 只在出现可重复工作流时增加新文档或脚本，避免为了目录完整而制造空洞文件。

## 最短反馈回路

```powershell
# 首次或依赖变化后
& .\.harness\scripts\bootstrap.ps1

# 普通代码改动的离线交付门槛
& .\.harness\scripts\check.ps1

# 涉及远端协议或归一化，并且 PaddleX 可用时
& .\.harness\scripts\smoke.ps1 -InputPdf "resources\...\sample.pdf"
```

离线测试不得访问真实 PaddleX。真实烟测生成的结果只允许写入 `output/smoke/`。
