# Remote Deploy and Smoke Workflow

本工作流用于把已通过本地检查的运行时代码部署到 T4 服务器，并执行真实验证。目标信息见
[`../operations/remote-targets.md`](../operations/remote-targets.md)。

1. 本地运行 `& .\.harness\scripts\check.ps1`。
2. 确认目标提交已推送，记录提交 SHA。
3. 只读检查远端：

   ```powershell
   ssh contractlens-t4 "cd /home/mineru_dev/projects/ContractLens && pwd && git status --short --branch"
   ```

4. 远端存在未提交改动、分支不符或目录不存在时停止。不得使用强制覆盖、`git reset --hard`
   或递归删除。
5. 确认远端分支后，必须先使用 fast-forward 同步代码，再验证 Compose 配置：

   ```powershell
   ssh contractlens-t4 "cd /home/mineru_dev/projects/ContractLens && git pull --ff-only && bash scripts/docker.sh config"
   ```

6. 配置验证成功后构建镜像并更新 FastAPI 容器，然后检查 Compose 状态：

   ```powershell
   ssh contractlens-t4 "cd /home/mineru_dev/projects/ContractLens && bash scripts/docker.sh build && bash scripts/docker.sh up && bash scripts/docker.sh ps"
   ```

   `uv sync --frozen` 只在 Dockerfile 的镜像构建阶段执行；T4 宿主机不单独同步 Python
   环境。不得用 `pkill`、递归删除或临时后台进程替代 Compose 管理。
7. 确认 `api` 容器处于运行且健康状态。若状态异常，读取有限尾部日志后停止部署并报告，
   不得循环重启：

   ```powershell
   ssh contractlens-t4 "cd /home/mineru_dev/projects/ContractLens && docker compose -f compose.yaml logs --tail 200 api"
   ```

8. 检查 `http://192.168.0.67:8888/openapi.json` 和
   `http://192.168.0.67:8880/health`。
9. 从本地运行 `.harness/scripts/smoke.ps1`，结果只写入 `output/smoke/`，并使用
   `validate_result.py` 校验契约。

日志和报告不得包含私钥、PDF Base64、Markdown 图片 Base64、完整远端响应或敏感正文。
