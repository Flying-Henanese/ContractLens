---
status: completed
owner: Codex
created: 2026-11-27
updated: 2026-11-27
scope:
  - paddleocr-server
  - pdf-parser-api
supersedes: []
blocked_by: []
---

# 共卡分支运行参数同步

## 目标与约束

将 `83d23bf` 的运行参数同步到 `codex/ascend-npu-colocated`。四个 PaddleX worker
与四个 vLLM DP rank 继续一一共用四张 NPU，并通过一个 vLLM API Server 推理。

## 实施与验收

1. 更新 Pipeline 功能开关、版面检测批量、VLM 并发和 Nginx 读取超时。
2. 同步 API 文档处理超时、预留票据超时及相应说明和测试。
3. 运行定向和完整检查，以 Ascend 模板渲染 Compose，核对四个 worker 的设备映射及 vLLM DP4。
   记录目标服务可用性及实际烟测范围。

## 进度与发现

- 目标分支从 `afe1148` 在独立工作树检出。源提交只改动 Pipeline YAML、Nginx 模板与 API。
- 共卡与分卡副本使用同一 Pipeline YAML。副本入口仅替换字面值 `max_concurrency: 16`，
  因此生成的配置会沿用 YAML 中的 `64`。
- 定向测试确认文档、票据和代理的旧时限会导致新断言失败；同步参数后通过。

## 决策与回滚

同步参数和与其直接相关的文档与测试。需要恢复时可以回退本次提交。

## 结果

- Harness 校验、Ruff 检查和全量离线测试通过，共 65 项测试。
- 使用 `.env.ascend.template` 渲染 Compose。配置测试核对了四个 worker 与 NPU 的映射、
  单 vLLM API Server 和 DP4。静态检查确认副本入口生成的 YAML 采用图表识别关闭、
  版面检测批量 `24`、VLM 并发 `64`。
- T4 的 CUDA 基准分支与本次目标不同。共卡模式的 Ascend 实机解析待验收。
