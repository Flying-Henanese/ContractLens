---
status: completed
owner: Codex
created: 2026-07-30
updated: 2026-07-30
scope:
  - container-deployment
  - compose
supersedes: []
blocked_by: []
---

# 昇腾环境容器支持

## 目标与用户价值

新增可在华为昇腾宿主机原生构建和运行的镜像定义，同时让 CUDA 与昇腾部署共享同一份 Compose 服务配置，避免两套配置随应用参数演进而漂移。

## 当前事实与约束

- 本仓库只调用远端 PaddleX Pipeline，容器内不执行 CUDA 或昇腾 NPU 推理。
- 现有 `Dockerfile` 使用 CUDA 12.2 基础镜像。
- 现有 `compose.yaml` 固定 `linux/amd64` 并预约 NVIDIA GPU，无法直接用于常见的昇腾 ARM64 宿主机。
- 应保留 T4 默认部署行为，且不得引入 CANN、VLM 或本地模型依赖。

## 实施阶段

- [x] 新增硬件无关、可原生支持 amd64/arm64 的 `Dockerfile.ascend`。
- [x] 让 `compose.yaml` 通过环境变量选择 Dockerfile，并移除应用不需要的硬件设备预约和固定平台。
- [x] 更新静态容器测试、环境变量示例和部署文档。
- [x] 验证 Compose 配置与仓库离线检查。

## 验证与验收

- `Dockerfile.ascend` 保持 builder/runtime 分离、非 root 用户和健康检查。
- 默认 Compose 仍选择 CUDA `Dockerfile`；昇腾部署可只通过 `.env` 切换。
- Compose 不包含 NVIDIA 或昇腾设备绑定，也不固定 CPU 架构。
- `uv run pytest tests/test_container_config.py` 与 `.harness/scripts/check.ps1` 通过。

## 进度记录

- 2026-07-30：确认应用为远端推理客户端，运行时不消费本机 GPU/NPU。

## 意外发现

- 当前 NVIDIA GPU 预约没有实际消费者，却使 Compose 无法跨硬件共享。

## 决策记录

- 共享 `compose.yaml`，仅用 `PDF_PARSER_DOCKERFILE` 和 `PDF_PARSER_IMAGE` 区分镜像。
- 昇腾镜像不安装 CANN；若未来将推理迁入本容器，应另立协议和运行时变更任务。
- 不设置 Compose `platform`，由 Docker 按宿主机原生架构构建。

## 恢复与回滚

删除 `Dockerfile.ascend` 并恢复 Compose 的固定 Dockerfile、平台和 NVIDIA 设备预约即可回到原部署定义；应用源码和输出契约不受影响。

## 结果总结

已新增 `Dockerfile.ascend`，并让 CUDA 与昇腾部署共享硬件无关的 `compose.yaml`。聚焦容器测试 5 项通过，Ruff 格式和 lint 通过，Compose YAML 静态解析通过。本机未安装 Docker CLI，未执行实际镜像构建或容器启动。完整离线测试为 45 项通过、1 项因既有未索引的 `2026-07-30-element-image-resources.md` 计划失败。
