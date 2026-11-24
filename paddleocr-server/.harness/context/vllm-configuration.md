# vLLM Configuration

CUDA 从 `vllm_config.yaml` 和入口脚本生成运行时配置。根 Ascend 使用 Compose 中的
`vllm serve` 命令行参数，详见 [运行配置](runtime-and-config.md#huawei-ascend)。以下 YAML
片段是模板初值，根 Compose 可按平台选择生效值。

## 模型与并行方式

```yaml
tensor-parallel-size: 1
data-parallel-size: 2
data-parallel-backend: mp
```

- `tensor-parallel-size: 1`：一个完整模型实例使用一张可见 GPU/NPU。
- `data-parallel-size: 2`：模板默认启动两个完整模型实例。
- `data-parallel-backend: mp`：单机使用多进程管理数据并行实例。

Pipeline 只配置一个 vLLM API 地址。vLLM 在该入口后调度多个 DP rank，不需要
额外的反向代理或手工维护多个服务地址。

运行时的 `data-parallel-size` 由 `VLM_DATA_PARALLEL_SIZE` 提供，根 Compose 默认
CUDA 为 `2`，Ascend 为 `3`。设备列表数量必须与模型实例数一致。

## 显存与调度

```yaml
gpu-memory-utilization: 0.8
max-num-seqs: 16
max-num-batched-tokens: 16384
```

- `gpu-memory-utilization` 控制每个实例可使用的显存比例；在昇腾环境中沿用该
  参数名，但对应 NPU HBM 使用比例。
- `max-num-seqs` 控制每个模型实例同时调度的最大序列数。
- `max-num-batched-tokens` 控制单轮调度允许的最大 token 批量。

三者需要和 Pipeline 的版面块并发、输入规模及设备容量一起压测。提高调度
上限可能改善吞吐，也可能增加显存/HBM、排队和尾延迟。

## 缓存与模型加载

```yaml
no-enable-prefix-caching: true
mm-processor-cache-gb: 0
trust-remote-code: true
```

- OCR 图片请求通常难以从前缀缓存获益，因此关闭前缀缓存。
- 多模态预处理器缓存设置为 0 GiB，避免长期占用内存。
- PaddleOCR-VL 需要加载模型仓库中的自定义实现，因此启用
  `trust-remote-code`。

CUDA 模板保留图执行的运行时默认值。Ascend 的图模式以命令行和实际启动日志为准。

## 环境变量覆盖

根 CUDA 入口脚本和根 Ascend Compose 使用：

```text
VLM_MODEL
VLM_DATA_PARALLEL_SIZE
VLM_DATA_PARALLEL_BACKEND
VLM_GPU_MEMORY_UTILIZATION
VLM_MAX_NUM_SEQS
VLM_MAX_NUM_BATCHED_TOKENS
```

CUDA 使用 `VLM_GPU_IDS`，昇腾使用 `VLM_NPU_IDS`。CUDA 入口脚本会拒绝以下配置：

- 数据并行大小不是正整数。
- 并行后端不是 `mp` 或 `ray`。
- 可见设备数量与数据并行实例数不一致。

CUDA 入口在容器启动时执行这些检查。根 Ascend 直接启动 vLLM，`VLM_MODEL` 用于
`--served-model-name`，本地权重路径由 Compose 的挂载和命令行决定。两平台的静态
Compose 解析均需配合部署前设备预检。

## 设备隔离

- 默认和普通副本部署的 Pipeline 与 VLM 设备分离。Ascend `colocated` 模式每卡部署
  一个 Pipeline worker 和一个 vLLM DP rank，共享一个 vLLM API Server。
- CUDA 通过 `CUDA_VISIBLE_DEVICES` 暴露物理 GPU。
- 昇腾通过 `ASCEND_RT_VISIBLE_DEVICES` 选择可见 NPU，副本的显式设备挂载与可见编号需在实机核对。
- 容器内设备会重新编号，Pipeline 使用 `gpu:0` 或 `npu:0` 是预期行为。
- `start_vl.sh` 会检查 CUDA 设备重叠；CUDA 和昇腾 Compose 当前不会交叉比较
  Pipeline 与 VLM 设备列表，需由部署者预检。

## 修改验证

修改 vLLM 配置后至少检查：

- `/v1/models` 健康检查正常。
- 每个预期设备加载一个完整模型实例。
- 所有 DP rank 在并发压测时均能承担负载。
- 没有 OOM/HBM OOM、调度超时或持续排队。
- 记录单实例/多实例下的吞吐、p50、p95 和设备利用率。
