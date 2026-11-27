---
status: completed
owner: Codex
created: 2026-11-27
updated: 2026-11-27
scope:
  - compose
  - deployment-workflow
supersedes:
  - root-compose-cuda-default
  - shell-selected-pipeline-topology
blocked_by: []
---

# 通过 `.env` 选择部署拓扑

## 目标与约束

在每台宿主机的根 `.env` 一次配置平台、拓扑和部署参数。根 Compose 默认加载昇腾四副本，T4 通过 `CONTRACTLENS_PLATFORM=cuda` 继续加载 CUDA。保留昇腾单 Pipeline 和两副本选择，复用原有服务配置和项目名。

当前脚本每次根据 Shell 环境选择拓扑。只读复现显示，从四副本配置启动后省略停机参数会选到 CUDA，四个 worker 都不在停机清单中。改成两副本后停机也会漏掉第三、第四个 worker。

## 实施与验收

1. 用已有 Compose 定义组成默认昇腾入口。用隔离目录中的真实 Compose CLI 验证默认、显式昇腾四副本、CUDA、昇腾单 Pipeline 和昇腾两副本，并检查同一 `.env` 的宿主机参数能传入服务。
2. 让脚本生命周期命令共同使用根入口，停机清理同一项目的孤儿容器。测试脚本发给 Docker 的参数，避免操作现场容器。
3. 更新模板、部署文档和 T4 流程，运行仓库完整离线门槛。

## 进度、发现与决策

- 已用 Compose 2.24.5 在临时目录验证，`include` 可根据 `.env` 选择平台，默认昇腾四副本解析出七个服务。
- 保留 `CONTRACTLENS_PIPELINE_MODE` 和 `CONTRACTLENS_PIPELINE_WORKERS` 作为昇腾拓扑变量，由 Compose 读取。继续使用 `contractlens` 项目名，便于识别现有容器。
- 现有 `.env.ascend` 可能含旧模板的 `single` 和 `2`。迁移指南明确区分原有宿主机参数和目标拓扑值。

## 恢复与回滚

需降低昇腾副本数时，在 `.env` 中设置两副本或单 Pipeline，并运行统一入口的 `config` 和 `up`。迁移前将旧 `.env.ascend` 中的实际参数合并到 `.env`，保留本机已有设置。

## 结果

- 已通过 15 项部署测试、Harness 结构检查、Ruff 和 Bash 语法检查。部署测试覆盖根 `.env` 的平台和副本选择、宿主机参数透传与停机参数。
- 解析后的 CUDA、昇腾单 Pipeline、昇腾两副本和昇腾四副本运行配置均与改动前对应拓扑一致。
- 全量测试 60 项通过，3 项 API 超时断言失败。使用改动前的 `b7ab2f0` 在隔离目录复现了相同的 3 项失败。
- 本机 Docker daemon 未运行。检查范围为 Compose 解析和脚本调用，昇腾实机启动、停机及解析烟测尚待验证。
