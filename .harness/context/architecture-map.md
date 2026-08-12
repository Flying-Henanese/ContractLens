# Architecture Map

## 运行组件

### PaddleOCR-VL API

- Compose 服务名：`paddleocr-vl-api`
- 对外默认端口：`8880`
- 容器内端口：`8080`
- 是单个前道服务，负责 API、文档预处理、PP-DocLayoutV3、版面框收集、版面块
  准备、子任务扇出和结果重组。
- CUDA 使用独立 Pipeline GPU；昇腾使用独立 Pipeline NPU。
- 当前由普通 `paddlex --serve` 启动，不是 PaddleX 高性能多 worker Serving。
  当前普通服务契约一次处理一个 `/layout-parsing` 请求；多个客户端请求只会
  增加在途和等待请求，不构成服务端文档并行。

### VLM Server

- Compose 服务名：`paddleocr-vlm-server`
- 内部端口：`8118`
- 提供 OpenAI-compatible `/v1` 接口。
- 使用 vLLM 启动一个或多个 PaddleOCR-VL-1.6-0.9B 完整模型实例。
- 模型实例数由 `VLM_DATA_PARALLEL_SIZE` 控制。
- 当前只暴露一个 VLM API 地址，vLLM 在该入口后调度多个 DP rank。

## 请求流

1. 客户端向 `/layout-parsing` 提交 Base64 文件和文件类型。
2. Pipeline 执行文档方向、展平等预处理。
3. PP-DocLayoutV3 识别版面区域并收集版面框。
4. VLM 准备阶段裁剪、合并和过滤版面块，并构造 VLM 请求。YAML 设置了
   `layout_prep_cpu_workers: 16`，但只有读取该字段的 PaddleX 版本才会并行执行
   页面准备；字段是否生效需要在目标镜像中确认。
5. `VLRecognition` 以 `max_concurrency` 将版面子任务扇出到 VLM Server。
6. vLLM 对请求执行连续批处理，并将其调度给多个数据并行模型实例。
7. Pipeline 重组页面和版面结果并返回响应。

## 设备映射

### CUDA

- 宿主机通过 `CUDA_VISIBLE_DEVICES` 暴露物理 GPU。
- 容器内部重新编号，因此只暴露一张 Pipeline 卡时使用 `gpu:0`。
- VLM 每个数据并行模型实例默认占用一张可见 GPU。

### 昇腾

- 宿主机通过 `ASCEND_RT_VISIBLE_DEVICES` 暴露物理 NPU。
- 容器内部重新编号，因此 Pipeline 使用 `npu:0`。
- Compose 挂载 Ascend driver、`npu-smi` 和 DCMI，并使用 `privileged`。

## 配置关系

- `VLM_GPU_IDS`/`VLM_NPU_IDS` 的数量必须等于
  `VLM_DATA_PARALLEL_SIZE`。VLM entrypoint 在容器启动时检查，Compose 静态
  解析不检查。
- Pipeline 设备不应与 VLM 设备重叠。宿主机 CUDA 入口 `start_vl.sh` 会拒绝
  重叠；两个 Compose 路径当前均不会执行这项交叉校验。
- `PaddleOCR-VL-1.6.yaml` 的 `server_url` 在 Compose 中指向服务名。
- `start_vl.sh` 会生成运行时 Pipeline 配置，将地址替换为
  `127.0.0.1:8118/v1`。
- `vllm_config.yaml` 是模板；入口脚本根据环境变量生成运行时配置。
- `use_queues: True` 使输入、CV 和 VLM 阶段通过内部队列重叠执行。
- `layout_prep_cpu_workers: 16` 是对支持该字段的 PaddleX 运行时提出的页面级
  CPU 准备 worker 上限，不控制 vLLM 模型实例数。在不支持该字段的版本中它会
  被忽略。

## 风险边界

- 单个前道 PP-DocLayout/API 服务是有意保留的架构边界，也可能成为吞吐瓶颈。
- 多个后端模型实例只有在前道能持续提供足够子任务时才能被充分利用。
- 数据并行只直接扩展 VLM 阶段，版面分析、预处理、结果重组或外层服务调度
  仍可能限制端到端吞吐。
- 模型、PaddleX、vLLM 和镜像版本之间存在兼容性约束。
- CUDA 与昇腾参数名可能相同但底层含义依赖运行时，例如昇腾仍沿用
  `gpu-memory-utilization`。
- Compose 设备权限、共享内存、驱动挂载和模型缓存属于已验证部署契约。
- 使用 `latest-*` 镜像意味着容器内实现可在仓库不变时变化；历史验证不能替代
  对当前镜像 ID/digest 的验证。
