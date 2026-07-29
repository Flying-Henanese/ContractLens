# Remote Targets

## T4 服务器

确认日期：2026-07-29

- SSH 配置别名：`contractlens-t4`
- 主机：`192.168.0.67`
- 用户：`mineru_dev`
- 项目目录：`/home/mineru_dev/projects/ContractLens`
- FastAPI：`http://192.168.0.67:8888`
- PaddleX：`http://192.168.0.67:8880`
- FastAPI 部署方式：仓库根目录的 `compose.yaml`
- Compose 项目名：`pdf-parser`
- Compose 服务名：`api`
- 生命周期入口：`bash scripts/docker.sh <config|build|up|ps|logs|restart|down>`

2026-07-29 用户确认 T4 已成功构建镜像并运行容器。远端代码更新分支仍须在每次部署前通过
只读检查确认，不得猜测。

SSH 私钥和 `IdentityFile` 只存在于用户本机的 SSH 配置，不写入仓库。
