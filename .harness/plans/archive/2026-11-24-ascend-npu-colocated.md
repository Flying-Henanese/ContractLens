---
status: completed
owner: Codex
created: 2026-11-24
updated: 2026-11-24
scope:
  - ascend-compose
  - paddleocr-server
supersedes: []
blocked_by: []
---

# 昇腾四卡共卡部署

## 目标与约束

增加可选的四卡部署模式。每卡运行一个 PaddleX worker 和一个 vLLM DP rank，四个
worker 共用一个 vLLM API Server。保留当前分卡拓扑、业务 API 和模型配置。
本地只执行静态检查，昇腾运行验证留给现场。

## 实施与验收

1. 从当前分支创建实验分支，记录共卡设计。
2. 扩展统一生命周期及 Compose overlay，解析后应正好有四个单卡 worker 及一个 DP4 VLM。
3. 更新部署指南和配置回归检查，验证共卡映射、默认及旧拓扑、非法设备列表。

## 进度、发现与决策

- 分支 `codex/ascend-npu-colocated` 已从当前 Ascend 副本分支创建。
- 旧副本配置的设备节点和运行时可见编号独立，因此共卡参数分别表达物理卡和两个运行时视图。
- CANN 要求 vLLM 的可见编号升序。入口脚本按数值排序 vLLM 的可见列表，保持各 worker 的映射顺序。

## 恢复与回滚

恢复原有 `single` 或 `replicas` 模式及其参数，使用根 `scripts/docker.sh up` 更新服务。

## 结果总结

共卡模式已实现。CUDA 单 Pipeline、Ascend 单 Pipeline、Ascend 两副本、Ascend 四副本和
Ascend 四卡共卡均通过 `docker compose config`。静态回归检查、Bash 语法、Ruff 和
Harness 校验通过。未启动容器、调用真实解析接口或运行吞吐压测。
