# Change Workflow

## 建立事实

1. 阅读根 `AGENTS.md`、harness 入口及任务路由的必要文档。
2. 运行 `git status --short`，保留无关用户改动。
3. 用 `rg` 定位实现、调用点、模型和测试，不凭文件名推断。
4. 明确验收标准、兼容边界和最小改动面。
5. 只有涉及服务参数或模型行为时才检查远端；普通测试保持离线。

## 决定是否写计划

跨越两个以上职责层，或修改协议、输出契约、失败策略、并发/提交模型、印章坐标、多阶段迁移时，按 [`../plans/CONVENTIONS.md`](../plans/CONVENTIONS.md) 建立并持续更新计划。局部低风险调整可直接实施，但仍需验证。

## 实施与测试映射

- 请求或响应形状：`tests/test_client.py`
- PDF 输入与校验：`tests/test_ingestion.py`
- 图像输入、签名和远端请求：`tests/test_image_input.py`
- 归一化、表格和印章：`tests/test_normalization.py`
- 文档编排、失败和页序：`tests/test_service.py`
- 跨页表格：`tests/test_cross_page_tables.py`
- CLI 或 API（包括文档类型路由）：对应 CLI/API 测试
- Harness 脚本与结构：`tests/test_harness.py`

先在最接近不变量的层修复根因，再更新调用方。用户可见行为变化同步 README；稳定架构变化同步 `architecture/`；远端观测只更新 `operations/`。

## 验证和交付

优先运行最接近改动的测试，完成后运行 `& .\.harness\scripts\check.ps1`。涉及真实远端时遵循 [`remote-validation.md`](remote-validation.md)。最终报告已实现结果、主要文件、实际运行的命令和未验证风险，不声称未运行的测试通过。
