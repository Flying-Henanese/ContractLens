# Pipeline Configuration

本文件记录 `PaddleOCR-VL-1.6.yaml` 中对官方 PaddleOCR-VL Pipeline 所做的
具体配置。配置文件本身是运行时事实源；修改参数后应同步更新本文件。

## 顶层配置

```yaml
pipeline_name: PaddleOCR-VL-1.6
batch_size: 64
use_queues: True
layout_prep_cpu_workers: 16
```

- `batch_size: 64`：Pipeline 顶层批处理配置。
- `use_queues: True`：启用输入、CV 和 VLM 阶段之间的内部队列流水线。
- `layout_prep_cpu_workers: 16`：这是运行时版本依赖项。支持该字段的 PaddleX
  以页面为任务并行完成过滤、裁剪、合并和 VLM 输入构造，实际 worker 数不超过
  当前页面数；不支持该字段的版本会忽略它。

本仓库的 CUDA 与昇腾镜像使用 `latest-*` 标签，无法仅从仓库锁定其中的
PaddleX 实现。启动目标镜像后应记录 PaddleX 版本，并通过源码、日志或性能指标
确认 `layout_prep_cpu_workers` 是否生效。不要把 YAML 中存在该字段作为生效证据。

`use_queues` 和 CPU 准备阶段的详细设计见
`../designs/2026-07-25-use-queues-pipeline.md`。

## 功能开关

```yaml
use_doc_preprocessor: True
use_layout_detection: True
use_chart_recognition: True
use_seal_recognition: True
format_block_content: True
merge_layout_blocks: True
```

- 开启文档预处理和 PP-DocLayoutV3 版面检测。
- 开启图表和印章识别。
- 格式化版面块内容并合并相关版面块。

## Markdown 忽略标签

以下标签不会进入最终 Markdown 主体：

```text
number
footnote
header
header_image
footer
footer_image
aside_text
```

这用于减少页码、页眉、页脚、脚注和旁注等内容对正文结果的干扰。

## PP-DocLayoutV3

版面检测模块使用：

```yaml
module_name: layout_detection
model_name: PP-DocLayoutV3
batch_size: 8
layout_nms: True
layout_unclip_ratio: [1.0, 1.0]
```

当前 25 个版面类别大多使用 `0.3` 阈值。`seal` 类别对应索引 `20`，阈值提高为
`0.9`，用于过滤不清晰或低置信度印章区域。

`layout_merge_bboxes_mode` 按类别选择：

- `large`：chart、display_formula、doc_title、inline_formula、
  paragraph_title 等更适合保留大框的类别。
- `union`：abstract、content、table、text、seal 等需要合并相邻框的类别。

修改阈值、NMS、unclip 或合框策略时，必须对对应版面类型进行样例回归，避免
版面块丢失、重复、错误合并或无效 VLM 请求增加。

## VLRecognition

```yaml
module_name: vl_recognition
model_name: PaddleOCR-VL-1.6-0.9B
batch_size: 4096
genai_config:
  backend: vllm-server
  server_url: http://paddleocr-vlm-server:8118/v1
  max_concurrency: 16
```

- VLM 推理由独立的 vLLM Server 提供。
- Compose 使用服务名访问；`start_vl.sh` 在运行时将地址替换为
  `http://127.0.0.1:8118/v1`。
- `max_concurrency: 16` 控制 Pipeline 同时提交的版面块请求数。
- `batch_size: 4096` 是模块批处理配置，不应直接解释为 4096 个并发 HTTP
  请求。

## 文档预处理

```yaml
DocPreprocessor:
  batch_size: 8
  use_doc_orientation_classify: True
  use_doc_unwarping: True
```

预处理阶段开启：

- 文档方向分类：`PP-LCNet_x1_0_doc_ori`
- 文档展平/畸变校正：`UVDoc`

这些操作发生在 PP-DocLayoutV3 版面分析之前。

## Serving

```yaml
Serving:
  visualize: false
  extra:
    max_num_input_imgs: null
```

- 禁用默认可视化和中间图片编码，减少非推理开销。
- 不在配置层限制输入图片数量；实际容量仍受服务、内存和超时约束。

## 修改验证

修改 Pipeline 配置后至少验证：

- PDF、图片和多页文档能够正常解析。
- 页面顺序、版面类别和结构化结果正确。
- 表格、公式、图表、图片和印章没有明显丢失或重复。
- Markdown 的页眉、页脚、页码和脚注过滤符合预期。
- 并发请求下无队列阻塞、串页或结果交叉。
- 前道 CPU、Pipeline GPU/NPU 和 VLM 设备负载符合预期。
- 如果验证 `layout_prep_cpu_workers`，使用多页输入并确认目标版本确实创建页面
  准备线程池；单页输入不会形成多个页面准备 worker。
