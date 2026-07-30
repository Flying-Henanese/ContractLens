---
status: complete
owner: Codex
created: 2026-07-30
updated: 2026-07-30
scope:
  - api
  - client
  - service
  - tests
  - docs
supersedes:
  - PDF-only document API input
blocked_by: []
---
# 文档解析接口支持 PDF 与图像

状态：complete

## 目标与用户价值

将 `POST /api/v1/documents/parse` 从仅接收 PDF 扩展为仅接收 PDF 或合法图像文件，并保持兼容 JSON 和 fail-fast 语义。

## 当前事实与约束

- 当前 API 仅接受 `.pdf`；服务层按页拆分 PDF，并通过 `fileType=0` 调用远端。
- 2026-07-30 已对 `http://192.168.0.67:8880/layout-parsing` 实测：PNG 的 `fileType=1` 成功；DOCX 和 DOC 均以 `422 Invalid input file` 被拒绝。
- 官方 PaddleX `layout-parsing` 服务契约仅接受 PDF 或图像（含 TIFF）。

## 实施阶段

- [x] 在输入和客户端边界区分 PDF 与图像，确保图像以 `fileType=1` 单次提交。
- [x] 扩展 HTTP 校验、离线单元测试和 API 文档。
- [x] 执行项目检查与远端 PNG 烟测。

## 验证与验收

- PDF 既有 API 测试和页面顺序测试保持通过。
- PNG/JPEG/TIFF/WEBP/BMP 在 API 边界被接收；不支持的格式被拒绝。
- 图像请求发送 `fileType=1`，并要求远端恰好返回一个结果。

## 进度记录

- 2026-07-30：建立计划；开始实施输入契约变更。

## 意外发现

- 暂无。

## 决策记录

- 复用现有 `ParseResponse`；图像作为单页文档返回 `page_num=1`。

## 恢复与回滚

只撤销本任务的源码、测试、文档和计划变更；不修改 `resources/` 或用户数据。

## 结果总结

已完成：文档接口支持受支持的 PDF 与图像输入；离线完整检查通过，远端 PNG 实测通过。
