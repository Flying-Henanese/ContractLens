# AGENTS.md

本文件适用于项目根目录及所有子目录，是 Codex 自动发现的仓库级指令入口。详细知识和可执行反馈位于 [`.harness/`](.harness/README.md)。

## 1. 项目边界

本项目是远端 PaddleX `PP-StructureV3` / `layout-parsing` Pipeline 的 PDF 文档解析客户端。模型推理在远端完成；本仓库负责 PDF 输入、HTTP 调用、结果归一化和兼容 JSON 输出。

- 当前版本只使用 PaddleX Pipeline 模式。
- 未经用户明确要求，不引入 VLM、多模态模型或外部 LLM。
- 不把 HTTP、PDF 输入、归一化、服务编排和 CLI/API 逻辑混入同一模块。
- 不把样例 JSON 当作绝对真值；其中可能包含 OCR 错字、坐标差异或模型幻觉。

当前架构、模块职责和稳定系统不变量以 [`.harness/architecture/`](.harness/architecture/README.md) 为唯一权威说明。

## 2. 修改前的必读与任务路由

开始修改前：

1. 阅读 [`.harness/README.md`](.harness/README.md)，按任务类型选择所需文档。
2. 运行 `git status --short`，保留无关的用户改动。
3. 实现、修复、重构或评审遵循 [`.harness/workflows/change.md`](.harness/workflows/change.md)。
4. 跨模块、协议、输出契约、失败策略或多阶段任务按 [`.harness/plans/CONVENTIONS.md`](.harness/plans/CONVENTIONS.md) 创建执行计划。
5. 涉及远端服务参数或模型行为时，读取 [`.harness/operations/remote-state.md`](.harness/operations/remote-state.md)，并重新检查实际服务。
6. 需要部署项目代码到 T4 服务器验证时，读取 [`.harness/operations/remote-targets.md`](.harness/operations/remote-targets.md)，并遵循 [`.harness/workflows/remote-deploy-and-smoke.md`](.harness/workflows/remote-deploy-and-smoke.md)。

用户当前任务中的明确要求优先于仓库文档；本文件与 `.harness/` 冲突时以本文件为准。

## 3. 开发环境

- Windows / PowerShell，Python `>=3.11`，依赖和虚拟环境使用 `uv`。
- 默认 PaddleX 地址为 `http://192.168.0.194:8080`。
- 默认关闭 `httpx` 系统代理继承，避免内网请求进入 `HTTP_PROXY`。
- 不直接使用系统 `pip`；依赖通过 `uv add`、`uv add --dev` 和 `uv sync` 管理。
- 源码、Markdown 和 JSON 使用 UTF-8，不因控制台乱码转换为 GBK。
- 网络代码保持异步；公共边界使用类型标注，结构化数据优先使用 Pydantic。
- 用户可见行为变化时同步更新 README 和相关测试。

## 4. 数据与安全

- 不修改、重命名或删除根目录及 `resources/` 中的用户 PDF、图片和样例 JSON，除非用户明确要求。
- 自动测试动态创建最小 PDF 或使用裁剪后的响应字典，不覆盖现有 `*_result.json`。
- 不提交 `.venv/`、临时目录、文档副本、大体积 Base64 或完整真实响应。
- 不在日志、异常或诊断文件中输出 PDF Base64、Markdown 图片 Base64、完整响应或敏感正文。
- 真实烟测结果只写入 `output/smoke/`；临时 PDF 或渲染图片放入 `tmp/pdfs/`。
- 当前失败策略为 fail-fast；页面或文档失败时不得输出伪装成成功的部分结果。

## 5. 交付门槛

优先运行与改动最接近的测试，交付前至少运行：

```powershell
& .\.harness\scripts\check.ps1
```

涉及远端协议、真实响应归一化或坐标时，在服务可用的前提下追加：

```powershell
& .\.harness\scripts\smoke.ps1 -InputPdf "resources\...\sample.pdf"
```

远端不可用时应明确报告未运行的验证，不得以模拟结果代替真实烟测。

## 6. 远端开发环境

- T4 服务器通过本机 SSH 配置中的 `contractlens-t4` 别名访问，仓库不保存私钥或私钥路径。
- 远端项目目录固定为 `/home/mineru_dev/projects/ContractLens`。
- 影响 FastAPI、PaddleX 请求、归一化或输出契约的改动，在本地门槛通过后按远端部署工作流验证。
- 部署前必须检查远端分支和工作区；存在未提交改动时停止，不得强制覆盖、清理或重置。
- 启动或重启远端服务前，必须在项目目录执行 `git pull --ff-only` 同步代码，再运行 `uv sync --frozen`。
- 服务管理方式未确认前，不得用 `pkill`、递归删除或临时后台进程冒充可靠重启。
