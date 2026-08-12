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

CV 阶段完成 PP-DocLayoutV3 和版面框收集后，VLM 准备阶段裁剪、合并和过滤
版面块，并构造 VLM 请求。配置模板包含 `layout_prep_cpu_workers: 16`；支持该
字段的 PaddleX 实现会以页面为任务使用 CPU 线程池，并把 worker 数限制为页面
数与配置值中的较小者。不支持该字段的 PaddleX 版本会忽略它。因此它是运行时
版本依赖项，不是仅凭本仓库 YAML 就能确认已启用的并发层。

### 1. 客户端请求压力

压测客户端可以同时向 `/layout-parsing` 发出多个 PDF/图片请求。当前 Compose
使用普通 `paddlex --serve`，不是高性能多 worker Serving；当前普通服务契约
一次处理一个完整 HTTP 请求。并发请求会增加在途和等待请求，因此客户端并发
表示施加的压力，不是服务端文档并行度。

压测脚本的 `--concurrency` 只控制客户端线程池。若要声称多个文档在服务端
并行，必须先改变 Serving 方案，并用运行时日志、指标或跟踪证明实际重叠执行。

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

- 当前正在处理的文档能够产生足够的页面或版面区域；若依赖多个文档共同供给，
  需先证明服务端确实会重叠执行这些请求。
- 单个前道 PP-DocLayout/API 服务能持续产生子任务。
- 当目标 PaddleX 支持时，`layout_prep_cpu_workers` 与单次 VLM 微批次页数及前道
  可用 CPU 核数匹配；否则该配置不参与吞吐形成。
- `max_concurrency` 足以将请求送入 vLLM。
- vLLM 调度参数足以形成有效批处理。
- 各模型实例有独立且足够的 GPU/NPU 显存或 HBM。

若单份文档版面元素很少，单次请求可能不足以填满多个模型实例。提高客户端
并发只能增加排队压力；普通 Serving 是否能借此让多个文档重叠处理必须实测，
不能从 `--concurrency` 静态推导。

## 常见瓶颈判断

### VLM 设备利用率低

- 检查客户端是否提供了足够工作，并确认服务端是否实际并行或仅排队。
- 检查每份文档产生的版面子图数量。
- 检查版面块 CPU 准备是否积压；若计划依赖 `layout_prep_cpu_workers`，先确认
  目标 PaddleX 读取该字段，再判断它是否与微批次页数和 CPU 资源匹配。
- 检查 `max_concurrency` 是否限制扇出。
- 检查单个前道是否在预处理或 PP-DocLayout 阶段饱和。

### VLM 排队且设备饱和

- 当前瓶颈位于 VLM 计算或调度。
- 在显存/HBM 允许时评估批处理参数。
- 对照增加模型实例数后的吞吐和尾延迟。

### 增加模型实例但吞吐不增长

- 检查单个前道服务是否已经饱和。
- 检查请求是否包含足够子任务。
- 检查版面块裁剪、合并、过滤和请求构造是否成为 CPU 瓶颈。
- 检查所有 DP rank 是否实际收到负载。
- 检查结果重组、编码或网络传输是否成为瓶颈。

### OOM 或高负载超时

- 降低 `gpu-memory-utilization`。
- 降低 `max-num-seqs` 或 `max-num-batched-tokens`。
- 降低 Pipeline 子任务并发或客户端请求并发。
- 如果已确认目标 PaddleX 启用了页面准备线程池，且前道内存压力来自该阶段，
  再评估降低 `layout_prep_cpu_workers`。
- 分别观察前道设备和 VLM 设备，不要混为同一资源池。

## 性能结论要求

至少记录：

- 平台、设备型号和设备数量。
- VLM 模型实例数。
- 客户端请求并发、服务端实际执行并行度、请求数和输入页数。
- `use_queues`、`layout_prep_cpu_workers` 是否生效、`max_concurrency`、
  `max-num-seqs`、`max-num-batched-tokens`。
- 成功率、错误类型、平均延迟、p50、p95、请求/秒和页/秒。
- 前道 CPU、前道 GPU/NPU 及每个 VLM 设备的利用率与内存/显存/HBM。

用单实例/多实例和低并发/高并发形成对照，不从单次结果推导扩展效率。
