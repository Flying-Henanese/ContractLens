# Concurrency Model

## 设计目标

本项目面向大批量文档解析。核心策略不是简单复制整套 PaddleOCR 服务，而是：

```text
一个 PaddleOCR API / PP-DocLayout 前道
  -> 将文档拆成大量版面子图任务
  -> 多个 vLLM 完整模型实例并行识别
```

这种设计让相对轻量且需要统一编排的前道任务保持单实例，同时把主要的 VLM
计算负载横向分布到多张 GPU/NPU。

## 三层并发

在以下三层业务并发之外，Pipeline 还通过 `use_queues: True` 将输入、CV 和 VLM
处理拆成内部队列流水线，使不同阶段可以重叠执行。详细设计见
`../designs/2026-07-25-use-queues-pipeline.md`。

### 1. 文档请求并发

多个 PDF/图片请求同时进入 `/layout-parsing`。它决定系统是否有足够多的文档
和页面可供前道处理，也是稳定填满后端 VLM 实例的重要来源。

压测脚本的 `--concurrency` 控制这一层。

### 2. 版面子任务并发

PP-DocLayoutV3 将页面拆成文本、表格、公式、图片等版面区域，Pipeline 再把
裁剪后的子图并发提交给 VLM。

`VLRecognition.genai_config.max_concurrency` 控制这一层。它是前道向后端扇出
任务的主要阀门。

### 3. vLLM 推理并行

后端有两种互补的并行能力：

- 每个模型实例通过连续批处理同时调度多个序列，主要由 `max-num-seqs` 和
  `max-num-batched-tokens` 控制。
- 多个完整模型实例通过 `data-parallel-size` 分布在不同 GPU/NPU 上。

当前实现中，多个实例位于同一个 vLLM API Server 入口之后。Pipeline 只配置
一个 `server_url`，不直接感知各 DP rank。

## 吞吐形成条件

要获得多实例收益，必须同时满足：

- 外层有足够的并发文档、页面或版面区域。
- 单个前道 PP-DocLayout/API 服务能持续产生子任务。
- `max_concurrency` 足以将请求送入 vLLM。
- vLLM 调度参数足以形成有效批处理。
- 各模型实例有独立且足够的 GPU/NPU 显存或 HBM。

若文档版面元素很少，单次请求可能不足以填满多个模型实例；此时应增加外层
文档并发，而不能只提高子图并发。

## 常见瓶颈判断

### VLM 设备利用率低

- 检查外层文档并发是否过低。
- 检查每份文档产生的版面子图数量。
- 检查 `max_concurrency` 是否限制扇出。
- 检查单个前道是否在预处理或 PP-DocLayout 阶段饱和。

### VLM 排队且设备饱和

- 当前瓶颈位于 VLM 计算或调度。
- 在显存/HBM 允许时评估批处理参数。
- 对照增加模型实例数后的吞吐和尾延迟。

### 增加模型实例但吞吐不增长

- 检查单个前道服务是否已经饱和。
- 检查请求是否包含足够子任务。
- 检查所有 DP rank 是否实际收到负载。
- 检查结果重组、编码或网络传输是否成为瓶颈。

### OOM 或高负载超时

- 降低 `gpu-memory-utilization`。
- 降低 `max-num-seqs` 或 `max-num-batched-tokens`。
- 降低 Pipeline 子任务并发或外层文档并发。
- 分别观察前道设备和 VLM 设备，不要混为同一资源池。

## 性能结论要求

至少记录：

- 平台、设备型号和设备数量。
- VLM 模型实例数。
- 外层请求并发、请求数和输入页数。
- `max_concurrency`、`max-num-seqs`、`max-num-batched-tokens`。
- 成功率、错误类型、平均延迟、p50、p95、请求/秒和页/秒。
- 前道及每个 VLM 设备的利用率与显存/HBM。

用单实例/多实例和低并发/高并发形成对照，不从单次结果推导扩展效率。
