# 昇腾四卡共卡部署

当前 Ascend 副本模式在一张卡上运行 2 或 4 个 PaddleX worker，vLLM 在其余卡上运行
DP rank。`colocated` 模式复用四副本 Nginx 拓扑，为每个 PaddleX worker 分配一张独立
物理卡，并在同一组卡上启动一个 vLLM API Server 的四个 DP rank（TP=1、DP=4、mp）。
PaddleX 共用同一个 VLM 服务地址，版面块由 vLLM 内部调度，不固定到同卡 rank。

物理设备列表与两个容器的 CANN 可见编号分开表示。部署脚本检查四个物理 ID 和四个
vLLM 可见 ID 各自唯一。每个 PaddleX 容器有独立的设备视图，其可见 ID 可以相同。
CUDA 与既有 Ascend 模式沿用原有 Compose 路径。

PaddleX CV 与 vLLM 识别可以重叠，同卡需要实测算力竞争及 HBM 峰值。静态验收覆盖
环境变量解析、Compose 设备与服务映射、代理依赖和 vLLM 启动参数。目标主机需进一步
确认实际物理卡与容器可见 ID 的对应、各 rank 推理和 PDF 解析质量。
