---
status: completed
owner: Codex
created: 2026-11-21
updated: 2026-11-21
scope:
  - harness
  - offline-checks
supersedes: []
blocked_by: []
---

# 对齐 Harness 与当前工作区实现

## 目标与用户价值

让网关契约、Compose 拓扑和检查流程与当前分支及工作区一致。

## 当前事实与约束

- 默认部署为单 Pipeline，当前分支提供 Ascend 2/4 worker overlay。
- 工作区已有 Ascend 镜像与设备映射改动，以及 T4 性能计划和临时文件。
- 整份 PDF 提交和 Ray Serve 不作为本次实施目标。

## 实施阶段

- [x] 对照网关、推理配置、Compose、测试和现有计划建立基线。
- [x] 修正架构、操作说明与计划状态，收敛质量门槛的检查范围。
- [x] 复核文档、运行离线门槛和 CUDA/Ascend Compose 静态检查。

## 验证与验收

运行 Harness lint、Ruff format/lint、pytest 和 diff check，解析 CUDA、
Ascend 单 Pipeline 及 2/4 worker Compose。

## 进度记录

- 2026-11-21：初始 Harness lint 和 51 项离线测试通过。
- 2026-11-21：对齐网关、默认 Compose 与 Ascend 副本拓扑；补充 T4 独立实验分支历史记录。

## 意外发现

- 初始 Ruff lint 与格式检查的所有失败均来自 tmp/ 下的未跟踪脚本。
- 当前 PaddleX 客户端会透传上游 `errorMsg`，且没有完整的嵌套响应类型校验。架构记录这
  两项边界，网关代码未变更。

## 决策记录

- 当前分支及工作区用于核对当前事实，其他分支实验和远端观测按各自证据范围引用。
- Ruff 排除根目录 `tmp/`，保留临时脚本和仓库代码的既有检查规则。

## 恢复与回滚

按本计划和 diff 恢复本次文档与检查配置，保留原有工作区改动。

## 结果总结

Harness 结构检查、Ruff format/lint 和 51 项离线测试通过。测试有一条既有第三方弃用警告。
本机缺少 PowerShell，使用 `uv run --no-sync --offline` 在现有虚拟环境逐项执行对应检查。
CUDA、Ascend 单 Pipeline 和 2/4 worker Compose 均通过静态解析。Bash 语法与
`git diff --check` 通过。本次未部署或运行真实解析烟测。
