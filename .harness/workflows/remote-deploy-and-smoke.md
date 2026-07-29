# Remote Deploy and Smoke Workflow

本工作流用于把已通过本地检查的运行时代码部署到 T4 服务器，并执行真实验证。目标信息见
[`../operations/remote-targets.md`](../operations/remote-targets.md)。

1. 本地运行 `& .\.harness\scripts\check.ps1`。
2. 确认目标提交已推送，记录提交 SHA。
3. 只读检查远端：

   ```powershell
   ssh "T4服务器" "cd /home/mineru_dev/projects/ContractLens && pwd && git status --short --branch"
   ```

4. 远端存在未提交改动、分支不符或目录不存在时停止。不得使用强制覆盖、`git reset --hard`
   或递归删除。
5. 确认远端分支后，必须先使用 fast-forward 同步代码，再同步锁定依赖。只有这一步成功后
   才能启动或重启服务：

   ```powershell
   ssh "T4服务器" "cd /home/mineru_dev/projects/ContractLens && git pull --ff-only && uv sync --frozen"
   ```

6. 按已确认的服务管理器重启 FastAPI。当前服务管理方式和服务名尚未记录，因此在补齐前不得
   自动杀进程或启动无人管理的后台进程。
7. 检查 `http://192.168.0.67:8888/openapi.json` 和
   `http://192.168.0.67:8880/health`。
8. 从本地运行 `.harness/scripts/smoke.ps1`，结果只写入 `output/smoke/`，并使用
   `validate_result.py` 校验契约。

日志和报告不得包含私钥、PDF Base64、Markdown 图片 Base64、完整远端响应或敏感正文。
