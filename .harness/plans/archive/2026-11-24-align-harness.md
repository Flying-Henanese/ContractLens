---
status: completed
owner: Codex
created: 2026-11-24
updated: 2026-11-24
scope:
  - harness
  - inference-harness
supersedes: []
blocked_by: []
---

# 对齐 Harness 与当前实现

## 目标与用户价值

同步网关和推理模块的 Harness，让后续开发和验证以当前分支的实际启动方式、参数和行为为依据。

## 当前事实与约束

起点为 `codex/ascend-pipeline-replicas` 的 `c84d721`，工作区干净。同步范围为两个 Harness；运行时代码、部署配置和已有测试作为核对依据。

## 实施阶段

- [x] 对照源码、Compose、入口脚本和离线测试建立基线。
- [x] 更新当前架构、推理参数、验证口径及受影响的进行中计划。
- [x] 执行离线门槛和静态配置核对，归档结果。

## 验证与验收

运行 Harness lint、Ruff、pytest、四种拓扑的 Compose 静态检查和 `git diff --check`。使用现有虚拟环境和 Bash 执行本机可用的等效检查。

## 进度记录

- 2026-11-24 完成初始审计，pytest 基线为 47 通过、4 失败。
- 2026-11-24 对齐 FastAPI 和 CLI 超时、双平台 vLLM 启动、Ascend 副本映射与 Pipeline 参数。
- 2026-11-24 用当前模板验证 `max_concurrency: 16` 的替换规则，候选值 `48` 仍生成 `32`。

## 意外发现

- 两项 API 测试仍期望 300 秒，两项 Ascend 副本测试仍期望可见设备 `7`。分支实际使用 600 秒和副本可见设备 `3`。
- 副本入口的字符串替换仍匹配 `max_concurrency: 16`，当前 YAML 的值已经是 `32`。

## 决策记录

- 当前参数引用源码与静态解析，远端观测和归档计划保留当时证据。

## 恢复与回滚

按本计划和 diff 恢复两个 Harness 的文档编辑。

## 结果总结

根 Harness lint、推理 Harness 本地链接、Ruff 格式与 lint、Shell 语法以及 `git diff --check`
通过。CUDA、Ascend 单 Pipeline 及 2/4 worker Compose 均通过静态解析，另核对了解析后的镜像、
启动命令、端口和设备映射。因为本机没有 PowerShell，使用现有虚拟环境和 Bash 运行对应检查。
pytest 仍为 47 通过、4 失败，与修改前基线一致。两项 API 断言和两项副本配置断言仍期望旧值。
本次未部署或运行真实解析烟测。
