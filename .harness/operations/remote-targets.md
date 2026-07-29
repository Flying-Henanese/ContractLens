# Remote Targets

## T4 服务器

确认日期：2026-07-29

- SSH 配置别名：`T4服务器`
- 主机：`192.168.0.67`
- 用户：`mineru_dev`
- 项目目录：`/home/mineru_dev/projects/ContractLens`
- FastAPI：`http://192.168.0.67:8888`
- PaddleX：`http://192.168.0.67:8880`

SSH 私钥和 `IdentityFile` 只存在于用户本机的 SSH 配置，不写入仓库。服务管理方式、服务名和
远端代码更新分支尚未确认；自动重启前必须补充这些信息，不得猜测。
