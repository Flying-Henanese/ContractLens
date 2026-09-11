# Remote Deploy and Smoke Workflow

本工作流用于把已通过本地检查的运行时代码部署到 T4 服务器，并执行真实验证。目标信息见
[`../operations/remote-targets.md`](../operations/remote-targets.md)。

1. 本地运行 `& .\.harness\scripts\check.ps1`。
2. 确认目标提交已推送，记录提交 SHA。
3. 只读检查远端：

   ```powershell
   ssh t4 "cd /home/mineru_dev/projects/ContractLens && pwd && git status --short --branch"
   ```

4. 远端存在未提交改动、分支不符或目录不存在时停止。不得使用强制覆盖、`git reset --hard`
   或递归删除。
5. 确认远端分支后，必须先使用 fast-forward 同步代码，再验证 Compose 配置：

   ```powershell
   ssh t4 "cd /home/mineru_dev/projects/ContractLens && git pull --ff-only && bash scripts/docker.sh config"
   ```

6. 配置验证成功后，按变更范围更新整套服务。仅在首次启动、`pyproject.toml`、`uv.lock`、
   Dockerfile 或镜像构建参数变化时构建网关镜像：

   ```powershell
   ssh t4 "cd /home/mineru_dev/projects/ContractLens && bash scripts/docker.sh build"
   ```

   无上述镜像输入变化时不构建。无论是否构建，都用同一生命周期入口更新并检查三个容器：

   ```powershell
   ssh t4 "cd /home/mineru_dev/projects/ContractLens && bash scripts/docker.sh up && bash scripts/docker.sh ps"
   ```

   `src/` 的网关代码由只读挂载和 Uvicorn reload 读取；`paddleocr-server/` 的入口和 Pipeline
   配置也由只读目录挂载读取，变更后须重启或更新相应容器以重新加载。`uv sync --frozen` 只在
   Dockerfile 的镜像构建阶段执行；T4 宿主机不单独同步 Python 环境。不得用 `pkill`、递归删除或
   临时后台进程替代 Compose 管理。
7. 确认 `api` 容器处于运行且健康状态。若状态异常，读取有限尾部日志后停止部署并报告，
   不得循环重启：

   ```powershell
   ssh t4 "cd /home/mineru_dev/projects/ContractLens && docker compose -f compose.yaml logs --tail 200 api"
   ```

8. 检查 `http://192.168.0.67:8888/openapi.json` 和
   `http://192.168.0.67:8880/health`。
9. 从本地运行 `.harness/scripts/smoke.ps1`，结果只写入 `output/smoke/`，并使用
   `validate_result.py` 校验契约。

日志和报告不得包含私钥、PDF Base64、Markdown 图片 Base64、完整远端响应或敏感正文。
