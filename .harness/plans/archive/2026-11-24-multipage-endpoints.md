---
status: completed
owner: Codex
created: 2026-11-24
updated: 2026-11-24
scope:
  - gateway-api
  - ingestion
  - paddlex-client
  - ascend-proxy
supersedes: []
blocked_by: []
---

# 整份与四段并发解析接口

## 目标与用户价值

提供可直接比较的同步 HTTP 入口。调用方复用上传格式和输出模型，以真实样本选择 PDF 提交策略。

## 当前事实与约束

- 现有 HTTP 和 CLI 将 PDF 逐页送往 PaddleX。PaddleX `/layout-parsing` 接收多页 PDF。
- Ascend 副本的 Nginx 按请求分流。代理请求体上限从 `64m` 调整为 `256m`。
- 保留已有端点、图像输入、页序、印章引用和整份失败语义。

## 实施阶段

- [x] 整份 PDF 原字节转发，并验证响应页数。
- [x] 连续页均分为最多四段，并发提交并以原文页码归一化。
- [x] 调整代理容量，完善调用说明并执行验证。

## 验证与验收

使用生成的最小 PDF 和模拟 PaddleX HTTP 响应核对新入口的请求体、请求数、并发、原文页码和失败响应。运行 Harness lint、Ruff、完整 pytest 和 Compose 配置检查。

## 进度记录

- 2026-11-24 确认需求和 HTTP 验证边界。
- 2026-11-24 桩响应验证整份及分段请求，补充非空分段、乱序返回、全局印章引用、图像和缺页失败覆盖。
- 2026-11-24 实现与兼容性复核后，补充新 PDF 入口的错误消息处理和性能字段说明。

## 意外发现

- 初始工作区保留前次 Harness 文档更新。两项超时断言和两项副本设备断言仍使用旧值。
- T4 使用 `codex/two-gpu-colocated-deployment`，有一个领先远端的提交。本次验证止于只读预检。

## 决策记录

- 新端点用 `/parse-whole` 和 `/parse-split`。分段页数最多相差一页，少于四页时只发非空分段；按原始页序归并。
- `PDF_PARSER_CONCURRENCY` 继续控制逐页入口，分段入口并发发送本次生成的所有段。

## 恢复与回滚

调用方可继续使用原 `/parse`。回滚本任务代码和代理配置时，保留任务开始前已有的工作区内容。

## 结果总结

Harness lint、Ruff、58 项离线测试、Shell 语法、CUDA 与 Ascend 单/双/四 Pipeline Compose 静态检查均通过。
本机无 PowerShell，逐项运行等效检查。T4 分支与本次分支不同，现场 Ascend 环境不可访问，未部署或执行真实解析烟测。
