---
status: completed
owner: Codex
created: 2026-11-13
updated: 2026-11-13
scope:
  - deployment
supersedes: []
blocked_by: []
---

# Ascend 多 Pipeline 静态适配

## 目标与用户价值

将 T4 多 Pipeline + Nginx 方案适配至 Ascend，交付同事进行硬件验收。

## 当前事实与约束

本地分支尚无 CUDA replicas 配置；从 T4 基准分支只读获取 Nginx 模板。
保留用户在 compose.ascend.yaml、active 计划和 tmp 中的既有改动。
不修改 Dockerfile、PaddleOCR 镜像、模型或 VLM 参数；没有可用 Ascend 主机。

## 实施阶段与进度记录

1. 新增 Ascend 2/4 worker overlay，完整覆盖代理服务，隔离 NPU 配置。
2. 新增 npu:0 入口、平台选择、环境模板及部署文档。
3. 用 Docker Compose 解析最终拓扑并执行离线门槛。

## 验证与验收

解析 2/4 worker，核对代理无 NPU、worker 无宿主机端口、保留 VLM DP3。
51 个离线测试通过；harness lint、Bash syntax、diff check 通过。
本机无 PowerShell，按 check.ps1 等价执行各项命令。全仓 Ruff 被原有 tmp 文件
的 13 个问题及两个文件的格式问题阻挡；排除 tmp 后 lint 和 33 个文件格式检查通过。
单 Pipeline、2/4 worker 的 Compose 配置均解析通过（本机 Compose 2.24.5）。
硬件启动、共享 NPU 容量、健康与真实 PDF 烟测由同事后续验证，不计为已通过。

## 意外发现与决策记录

本机 Bash 3 对 nounset 下空数组的展开不兼容，统一入口改用兼容展开。
本机 Compose 2.24.5 devices JSON 为字符串，测试兼容字符串和结构化两种格式。
保持默认单 Pipeline。多副本共享原 Pipeline NPU；不采用 CUDA 共置 VLM 方案。

## 恢复与回滚

通过 single 模式运行统一 up 恢复原服务并移除副本。

## 结果总结

静态实现完成；Ascend 验收待执行。指南含交接步骤与验证边界。
