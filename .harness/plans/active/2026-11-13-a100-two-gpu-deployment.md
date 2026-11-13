---
status: active
owner: Codex
created: 2026-11-13
updated: 2026-11-13
scope:
  - deployment
  - build
supersedes: []
blocked_by: []
---

# A100 双卡部署

## 目标与用户价值

在a100的/home/mineru_dev/github/contractlens拉取双卡分支，用原Dockerfile构建网关镜像，
使用空闲GPU2/3启动2 Pipeline + TP1/DP2，并验证最小请求。

## 当前事实与约束

目录原为空，已克隆codex/two-gpu-colocated-deployment/cd4a7f3；工作区干净。
A100 80GB×4，0/1被其他项目使用，2/3空闲；驱动550.54.15，Compose2.29.1配置检查通过。
不改Ascend、宿主驱动、其他服务；不做整书压测。无宿主uv sync。

## 实施阶段

1. 检查仓库/GPU/端口，准备独立.env.two-gpu，拉取固定镜像与模型。
2. 构建原Dockerfile；解决构建专属资源上限，再构建。
3. 统一入口up，检查5服务健康、GPU映射及一页临时PDF API烟测。
4. 保存操作证据和远端状态，不改之前交付包或T4运行服务。

## 验证与验收

镜像内容与T4一致，权重/配置SHA256一致；本地静态门槛通过；A100原Dockerfile构建成功；
5服务healthy，模型仅用GPU2/3，API单页严格契约通过。不可用则记录真实失败，不伪称完成。

## 进度记录

- 首次公网拉取很慢，复用T4镜像，经一次性仅允许A100的内网传输导入，监听已关闭。
- 权重副本已同步且用户确认使用，model.safetensors/config.json与T4 SHA256一致。
- Torch2.8.0+cu128容器在GPU2/3识别2张A100并成功运行张量运算。
- 原构建失败在uv编译Python3.11.15标准库：EMFILE。
- 最小BuildKit探针确认软nofile1024、硬524288；普通运行容器为1048576；宿主全局文件表未耗尽。

## 意外发现

高核数主机上的BuildKit构建软nofile上限不足，不是模型/GPU内存问题。

## 决策记录

只在共置overlay的api.build.ulimits设置nofile软硬65536，不改Dockerfile、主机及其他平台。

## 恢复与回滚

用scripts/docker-two-gpu.sh down停止本项目；旧T4配置与其他项目不受影响。
构建修复可回退单一overlay字段，不需要驱动或系统参数变更。

## 结果总结

部署进行中。
