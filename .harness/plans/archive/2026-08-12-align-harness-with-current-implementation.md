---
status: completed
owner: Codex
created: 2026-08-12
updated: 2026-08-12
scope:
  - harness-architecture
  - harness-invariants
  - harness-validation-workflow
  - active-plan-state
  - image-document-path
supersedes:
  - overclaimed-coordinate-bounds
  - overclaimed-seal-deduplication
  - inaccurate-text-fallback-order
  - validator-equals-public-contract
blocked_by: []
---
# 对齐 Harness 与当前实现

## 目标与用户价值

仅修改 `.harness/` 内的 Markdown，使架构、不变量、验证流程和 active plan 状态准确描述
当前代码；不修改应用源码、测试、脚本、README 或远端状态。

## 当前事实与约束

- 普通版面元素沿用 PaddleX 坐标，不裁剪到页面范围；印章区域和印章文字坐标在已知页面尺寸时
  才会裁剪。
- 当前按远端返回的印章结果或检测框逐项生成 `SealDetail`，不对重复物理框去重。
- 版面块存在时，正文不会把未落入块内的整体 OCR 作为额外回退；仅当没有版面详情时整体
  OCR 才生成详情，组装后仍为空才回退 Markdown。
- `validate_result.py` 是严格的真实烟测质量门槛，会拒绝部分 Pydantic 模型可表达的结果，
  不能等同于生产公共模型。
- `service.py` 和 `ingestion/pdf.py` 当前都会读取并校验 PDF；这是现状，不在本任务中重构。
- 整份 PDF 提交仍未实现；原 active plan 保持目标计划身份，但需更新复核日期和当前状态说明。
- 推送前同步远端发现当前实现已增加图像文档路径；最终 Harness 同时记录 PDF 与图像输入事实。

## 实施阶段

- [x] 修正 `architecture/README.md` 的模块职责、正文回退、坐标和印章去重描述。
- [x] 收窄 `architecture/invariants.md`，只保留实现真正保证的行为并列出明确非保证项。
- [x] 在 harness 入口和远端验证流程中区分公共 Pydantic 结构与严格烟测门槛。
- [x] 更新整份 PDF active plan 的复核时间，但不改变目标或虚构进度。
- [x] 运行 Harness 结构检查、定向测试和完整离线门槛。

## 验证与验收

- `git diff` 只能包含 `.harness/**/*.md`。
- `uv run python .harness/scripts/harness_lint.py` 通过。
- `uv run pytest tests/test_harness.py` 通过。
- 完整 `.harness/scripts/check.ps1` 等价门槛通过；非 Windows 环境直接运行其中的同等命令。
- 最终文档不再声称普通坐标必定位于页面内、物理印章已去重、整体 OCR 总会位于 Markdown
  之前，或烟测验证器等同于生产模型。

## 进度记录

- 2026-08-12 — 根据审查结论建立计划；工作区初始无未提交改动。
- 2026-08-12 — 架构、不变量、验证流程和既有 active plan 已按当前实现更新；Harness 结构
  检查通过，`tests/test_harness.py` 5 项通过，`git diff --check` 通过。
- 2026-08-12 — 完整等价门槛通过：Harness 校验、Ruff format/lint 和 42 项离线测试通过；
  仅有一个既有 Starlette/httpx 第三方弃用警告。因本机没有 PowerShell，直接运行了
  `check.ps1` 中对应的四条 `uv run` 命令。
- 2026-08-12 — 推送前发现 `origin/main` 前进 4 个提交；rebase 后补充图像文档数据流、
  `fileType=1` 协议、图像测试映射和远端已有 active plan 索引；最终完整门槛 46 项离线测试
  通过，仅有同一个既有第三方弃用警告。

## 意外发现

- `architecture/README.md` 初稿重复了 `invariants.md` 的稳定规则；双轴复审发现后已收敛为摘要
  和链接，继续维持单一权威位置。
- Harness 入口初稿重复了远端验证 workflow 的严格验证项；复审后入口仅保留职责区别和链接，
  具体验收规则只在 workflow 维护。
- 定向 pytest 的自定义 `--basetemp` 留下未跟踪临时目录；确认内容仅为本次测试产物后已删除。

## 决策记录

- 决策：保留严格烟测验证器的现有行为，只在文档中准确界定其职责。
  理由：用户要求不修改代码；严格质量门槛可以有意窄于生产 Pydantic 模型。
  日期：2026-08-12。
- 决策：不替用户取消整份 PDF 提交目标，只补充本次复核证据。
  理由：目标是否取消属于产品决策；当前任务只要求 Harness 反映真实实现。
  日期：2026-08-12。

## 恢复与回滚

中断后以本计划和 `git diff -- .harness` 为准继续。所有修改均为 `.harness/` Markdown，
可逐文件恢复，不涉及应用代码、用户样本或远端状态。

## 结果总结

Harness 已与当前代码对齐：记录双重 PDF 读取/校验、真实正文回退分支、普通版面坐标不裁剪、
印章条目不做物理去重、图像文档单页处理路径，以及严格烟测验证器窄于生产 Pydantic 模型。
整份 PDF 提交计划仍保持 active，但已明确截至 2026-08-12 尚未实施。

验证：Harness 结构检查通过；定向 Harness 测试 5 passed；同步最新 `origin/main` 后的最终完整
等价门槛中 Ruff format/lint 通过、离线测试 46 passed（1 个既有第三方弃用警告）；
`git diff --check` 通过；Standards/Spec
双轴复审及两轮 Standards 复查发现的重复权威、重复表述和临时目录问题均已修正，最终复查
没有硬性问题。改动仅包含 `.harness/**/*.md`。
