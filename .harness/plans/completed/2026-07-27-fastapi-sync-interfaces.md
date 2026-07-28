# FastAPI 同步识别接口

状态：completed
负责人：Codex
创建日期：2026-07-27
最后更新：2026-07-27 +08:00

## 目标与用户价值

为现有 PDF Parser 增加可供外部系统调用的 FastAPI 服务。文档接口同步等待现有
PaddleX 解析完成，单页远端请求超时为 300 秒；票据接口接受 PDF 或图片文件，
预留 120 秒超时配置，但本次不实现识别逻辑。

不改变现有 CLI、PaddleX 请求协议、归一化结果和 fail-fast 行为。

## 当前事实与约束

- `src/pdf_parser/service.py::parse_pdf` 是异步文档级编排入口，只接受本地 PDF 路径。
- FastAPI 路由按用户要求使用同步 `def`，由同步路由内部建立事件循环调用现有服务。
- 上传内容必须写入隔离的临时目录，并在请求结束后清理；不能覆盖用户样本或输出。
- 当前产品只能解析 PDF 文档。票据接口允许 PDF 和常见图片类型，但返回明确的未实现错误。
- 上传表单除 FastAPI 外还需要 `python-multipart`，服务启动需要 ASGI server。

## 实施阶段

- [x] 阶段 1：加入 FastAPI、上传表单和 ASGI server 依赖。
- [x] 阶段 2：实现文档与票据同步路由、类型校验、超时和错误映射。
- [x] 阶段 3：补充离线 API 测试和 README 启动/调用说明。
- [x] 阶段 4：运行 harness 完整检查并归档计划。

## 具体改动

- 新增 `src/pdf_parser/api.py`，包含应用工厂、同步路由和上传临时文件边界。
- 新增 `tests/test_api.py` 和 `tests/test_api_timeout.py`，mock 现有解析入口，不访问真实 PaddleX。
- 更新 `pyproject.toml`、`uv.lock`、README、`docs/api.md` 和架构文档。

## 验证与验收

```powershell
uv run pytest tests/test_api.py --basetemp .pytest-tmp-api
& .\.harness\scripts\check.ps1
```

测试覆盖同步路由定义、300/120 秒配置、文档成功响应、非法类型、空文件、领域错误映射，
以及票据占位响应。本次不需要真实远端烟测，因为 PaddleX 请求协议和归一化逻辑不变。

## 进度记录

- 2026-07-27 — 已检查 AGENTS、harness、项目结构和工作区；开始实现依赖与 API 边界。
- 2026-07-27 — API 专项测试 7 项通过。
- 2026-07-27 — harness Full 检查通过：格式、lint 和 25 项离线测试全部通过。

## 意外发现

- 当前 Git 工作区全部文件均为未跟踪状态；本任务只新增或修改明确列出的项目文件。

## 决策记录

- 决策：使用 FastAPI 同步 `def` 路由，并在文档路由中调用 `asyncio.run(parse_pdf(...))`。
  理由：满足同步请求语义，同时保持现有网络客户端与服务编排的异步边界。
  日期：2026-07-27
- 决策：票据接口返回 HTTP 501，不返回伪成功结果。
  理由：识别逻辑尚未实现，明确失败符合项目 fail-fast 原则。
  日期：2026-07-27

## 恢复与回滚

中断后从 `src/pdf_parser/api.py` 和 `tests/test_api.py` 继续。回滚时只移除本任务新增 API
文件及依赖/文档增量，不改动现有解析链路和用户样本。

## 结果总结

已增加两个同步 FastAPI 路由。文档路由安全使用临时文件，300 秒内同步返回现有兼容
JSON，并映射 400/502/504 错误；票据路由接受 PDF 和常见图片，配置 120 秒超时并以
HTTP 501 明确标识逻辑待实现。依赖、锁文件、API 文档、架构文档和离线回归测试均已同步。
