# Remote Targets

## T4 服务器

确认日期：2026-07-29（以下为合并前观测；统一 Compose 尚未在目标服务器验证）

- SSH 配置别名：`contractlens-t4`
- 主机：`192.168.0.67`
- 用户：`mineru_dev`
- 项目目录：`/home/mineru_dev/projects/ContractLens`
- FastAPI：`http://192.168.0.67:8888`
- PaddleX：`http://192.168.0.67:8880`
- FastAPI 部署方式：仓库根目录的 `compose.yaml`
- 合并前 Compose 项目名：`pdf-parser`
- 合并前 Compose 服务名：`api`
- 统一 Compose 的预期服务：`api`、`paddleocr-vl-api`、`paddleocr-vlm-server`
- 统一生命周期入口：`CONTRACTLENS_PLATFORM={cuda|ascend} bash scripts/docker.sh <config|build|up|ps|logs|restart|down>`

2026-07-29 用户确认合并前的网关镜像已成功构建并运行。统一 Compose 仅完成离线粘合，尚未在
T4 上执行 Docker 配置、启动或解析验证；远端代码更新分支仍须在每次部署前通过只读检查确认，
不得猜测。

SSH 私钥和 `IdentityFile` 只存在于用户本机的 SSH 配置，不写入仓库。
