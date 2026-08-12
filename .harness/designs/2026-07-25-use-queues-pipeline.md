# `use_queues` Pipeline 流水线设计

## 背景

本项目使用一个 PaddleOCR API/PP-DocLayoutV3 前道服务，将文档拆成版面子图，
再把子图并发发送给后端多个 vLLM 模型实例。

`PaddleOCR-VL-1.6.yaml` 中启用了：

```yaml
use_queues: True
layout_prep_cpu_workers: 16
```

## 当前实现状态

本设计包含两个性质不同的配置：

- `use_queues` 是已在 PaddleX 正式版本中存在的 Pipeline 行为。
- `layout_prep_cpu_workers` 是运行时版本依赖项。支持它的 PaddleX 会按页面使用
  CPU 线程池；不支持它的版本会忽略该字段。本项目使用 `latest-*` 镜像，必须
  在目标镜像中确认 PaddleX 版本和该字段是否生效。

当前 API 使用普通 `paddlex --serve`，不是高性能多 worker Serving。本设计中的
输入、CV、VLM 队列描述单次 Pipeline 调用内部的阶段重叠，不表示多个完整
`/layout-parsing` 请求会在服务端并行执行；当前普通服务契约一次处理一个请求。

`use_queues` 用于开启 PaddleOCR-VL Pipeline 内部的队列化流水线，使输入、CV
和 VLM 三个阶段通过队列传递中间结果。它解决的是单个 Pipeline 内不同处理
阶段之间的重叠执行问题。

在支持该字段的 PaddleX 中，`layout_prep_cpu_workers` 控制 VLM 请求发出前的
页面级 CPU 准备并发，包括版面块裁剪、合并、过滤和请求构造。它不控制
PP-DocLayoutV3 推理线程数，也不控制后端 vLLM 模型实例数；实际 worker 数还
受当前微批次页面数限制。

## 阶段与队列

```text
输入线程
  PDF 拆页 / 图片加载
        │
        ▼ queue_input
CV 线程
  图片解码
  → 可选文档预处理
  → PP-DocLayoutV3
  → 收集版面框
        │
        ▼ queue_cv
VLM 线程
  裁剪版面块
  → 合并/过滤版面框
  → 构造 VLM 请求
  → 并发请求 vLLM
  → 等待该微批次全部块完成
  → 聚合页面结构化结果
        │
        ▼ queue_vlm
返回 JSON / Markdown
```

### 输入阶段

输入线程负责读取图片，或将 PDF 拆分为页面，并把可处理的输入送入
`queue_input`。输入读取不必等待后续页面完成 CV 和 VLM 推理后才继续。

### CV 阶段

CV 线程从 `queue_input` 消费任务，完成图片解码、可选文档预处理和
PP-DocLayoutV3 版面分析，然后将页面及其版面框送入 `queue_cv`。

这是项目中的单前道 PP-DocLayout 阶段。它能与输入和 VLM 阶段重叠执行，
但仍可能在高负载下成为整体吞吐瓶颈。

### VLM 阶段

VLM 线程从 `queue_cv` 消费结果，裁剪、合并和过滤版面块，构造 VLM 请求并
按照 `VLRecognition.genai_config.max_concurrency` 并发请求后端。

`layout_prep_cpu_workers: 16` 配置在 Pipeline YAML 顶层。目标 PaddleX 若支持
该字段，会用最多 16 个 CPU worker 按页面并行完成版面块裁剪、合并、过滤及
VLM 请求准备；worker 数不会超过参与该批次的页面数。旧版本忽略该字段。

当前后端是单一 vLLM API 入口，入口后由多个数据并行模型实例处理请求。VLM
线程等待当前微批次中的版面块全部完成，再聚合为页面结构化结果并送入
`queue_vlm`，最终生成 JSON 或 Markdown。

## 并发模型中的位置

`use_queues` 增加的是 Pipeline 内部阶段并行。它与其他并发机制互补，但语义
不同：

| 机制 | 控制范围 | 主要作用 |
| --- | --- | --- |
| `use_queues` | 单个 Pipeline 内部 | 让输入、CV、VLM 阶段重叠执行 |
| `layout_prep_cpu_workers` | 支持该字段的 PaddleX 中，VLM 请求前的页面准备 | 页面级并行裁剪、合并、过滤版面块并构造请求 |
| 客户端请求并发 | 压测客户端线程池 | 同时发出请求；不保证服务端并行执行 |
| `max_concurrency` | Pipeline 到 VLM | 控制同时发出的版面块请求数 |
| `max-num-seqs` | 单个 vLLM 模型实例 | 控制实例内同时调度的序列数 |
| `max-num-batched-tokens` | 单个 vLLM 模型实例 | 控制每轮调度的 token 批量 |
| `data-parallel-size` | vLLM 后端 | 控制完整模型实例数量 |

因此：

- `use_queues: True` 不会自动增加 vLLM 模型实例数。
- `layout_prep_cpu_workers` 不会增加 PP-DocLayoutV3 或 vLLM 模型实例数。
- `use_queues` 不等同于 HTTP 服务并行处理多个请求。
- `use_queues` 不会消除单个 PP-DocLayout/CV 阶段的计算上限。
- `use_queues` 能减少各阶段相互等待，使输入、版面分析和 VLM 推理形成流水线。
- 后端 VLM 是否能被充分利用，仍取决于文档量、版面块数量、
  `max_concurrency` 和 vLLM 调度能力。

## 当前决策

保持 `use_queues: True`，因为项目目标是大规模并行处理，而队列化 Pipeline
可以让前道输入、CV 版面分析和后端 VLM 推理尽可能重叠。

当前同时设置 `layout_prep_cpu_workers: 16`。CUDA 和昇腾 Compose 都挂载同一
份 `PaddleOCR-VL-1.6.yaml`，但两种环境只有在各自镜像内 PaddleX 支持该字段时
才会启用页面准备线程池。

`use_queues` 是否调整应根据目标 PaddleOCR/PaddleX 版本上的兼容性、死锁、资源
占用和结果一致性证据决定。`layout_prep_cpu_workers` 的调优必须先确认字段生效。

## 调优和排障

### VLM 设备空闲

检查：

- 输入阶段是否持续产生页面。
- CV/PP-DocLayout 阶段是否已经饱和。
- 目标 PaddleX 是否读取 `layout_prep_cpu_workers`；若读取，worker 上限是否与
  当前微批次页数及前道可用 CPU 核数匹配。
- 版面块裁剪、合并、过滤及请求准备是否积压。
- 文档是否产生足够多的版面块。
- `max_concurrency` 是否过低。

### 队列流水线运行但吞吐不增长

`use_queues` 只能重叠阶段，不能突破最慢阶段的计算上限。应分别观察输入、CV
和 VLM 阶段，判断瓶颈位于：

- PDF 拆页或图片加载。
- 文档预处理或 PP-DocLayoutV3。
- 版面块裁剪、合并、过滤、请求构造及结果聚合。
- vLLM 排队或模型推理。

### 延迟和内存上升

高并发会增加在途页面、图片、版面框和 VLM 请求数量。出现 OOM、HBM OOM、
超时或尾延迟显著上升时，应联合降低：

- 客户端请求并发。
- 已确认生效时的 `layout_prep_cpu_workers`。
- `VLRecognition.genai_config.max_concurrency`。
- vLLM 的 `max-num-seqs`。
- vLLM 的 `max-num-batched-tokens`。

不要仅通过关闭 `use_queues` 掩盖下游容量不足；应先定位具体拥塞阶段。

## 验证要求

修改 `use_queues` 或相关并发参数后，至少验证：

- PDF 和图片均能正常返回 JSON/Markdown。
- 多页 PDF 的页面顺序和聚合结果正确。
- 表格、公式、图片、印章等版面块没有丢失或串页。
- 多页输入下无队列阻塞、死锁或长期不返回；客户端并发测试需区分排队与实际
  服务端并行。
- 对比开启与关闭时的请求吞吐、页吞吐、p95 延迟和内存占用。
- 记录镜像 ID/digest、PaddleX 版本、`layout_prep_cpu_workers` 是否生效、微批次
  页数、前道可用 CPU 核数和 CPU 利用率。
- 观察前道 CPU、前道 GPU/NPU 和所有 VLM 设备的实际利用率。
