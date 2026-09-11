# Remote Targets

## T4 服务器

确认日期：2026-09-11

- SSH 配置别名：`t4`
- 主机：`192.168.0.67`
- 用户：`mineru_dev`
- 项目目录：`/home/mineru_dev/projects/ContractLens`
- FastAPI：`http://192.168.0.67:8888`
- PaddleX：`http://192.168.0.67:8880`
- CUDA vLLM 诊断端口：`http://192.168.0.67:8118`
- 部署方式：仓库根目录的 `compose.yaml`（CUDA）或 `compose.ascend.yaml`（Ascend）
- 统一 Compose 服务：`api`、`paddleocr-vl-api`、`paddleocr-vlm-server`
- 统一生命周期入口：`CONTRACTLENS_PLATFORM={cuda|ascend} bash scripts/docker.sh <config|build|up|ps|logs|restart|down>`

2026-09-11 已在 T4 CUDA 环境完成一次统一 Compose 启动、端点检查和真实解析烟测；镜像、GPU
分配、端口和当前在线状态属于易变观测，唯一记录见 [`remote-state.md`](remote-state.md)。每次部署
前仍须只读确认远端分支、工作区、端口和容器状态，不得从这次成功验证推断当前服务仍在运行。

SSH 私钥和 `IdentityFile` 只存在于用户本机的 SSH 配置，不写入仓库。
