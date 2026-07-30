---
status: complete
owner: Codex
created: 2026-07-30
updated: 2026-07-30
scope:
  - compose
  - container-runtime
  - tests
  - docs
supersedes:
  - image-only source delivery during active iteration
blocked_by: []
---
# Compose 开发期源码挂载

状态：complete

## 目标与用户价值

在频繁迭代阶段，让 Compose 容器使用仓库的 `src/` 只读挂载，并通过 Uvicorn 自动重载在代码变化后加载新实现，无需每次重建或重新创建容器。

## 当前事实与约束

- 当前镜像在构建阶段将 `src/` 打包进虚拟环境；Compose 没有代码卷挂载。
- 容器以非 root 用户运行，根文件系统为只读，`/tmp` 由 tmpfs 提供。
- 仅挂载代码不能让正在运行的 Python 进程自动加载修改；开发 Compose 应覆盖入口为带 `--reload` 的 Uvicorn。
- 依赖、Dockerfile、Compose 配置或环境变量变更仍须重新构建或重新创建容器。

## 实施阶段

- [x] 在 `compose.yaml` 添加 `/app/src` 只读 bind mount，并以 Uvicorn reload 入口启动。
- [x] 更新容器配置测试和部署文档，清晰区分代码改动与镜像/配置改动的操作。
- [x] 校验 Compose 渲染、离线检查和容器相关测试。

## 验证与验收

- Compose 配置包含只读 `./src:/app/src` 挂载和受限到 `/app/src` 的 Uvicorn reload。
- 保持 UID、只读根文件系统、tmpfs、GPU 预约和端口映射不变。
- `& .\.harness\scripts\check.ps1` 通过。

## 进度记录

- 2026-07-30：建立计划，开始实施开发期源码挂载。

## 意外发现

- 暂无。

## 决策记录

- 在当前唯一 Compose 文件中启用开发期挂载和自动重载；镜像仍保留完整依赖与打包代码，便于切回镜像交付。

## 恢复与回滚

移除 Compose 的 bind mount 和 entrypoint 覆盖即可恢复镜像内代码运行模式。

## 结果总结

已完成：Compose 使用只读源码挂载、PYTHONPATH 与受限目录自动重载；容器测试和完整离线检查通过。
