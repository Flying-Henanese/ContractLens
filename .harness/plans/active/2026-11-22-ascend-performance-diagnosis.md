---
status: active
owner: Codex
created: 2026-11-22
updated: 2026-11-27
scope:
  - ascend-runtime
  - paddleocr-server
  - inference-benchmark
supersedes: []
blocked_by: []
---

# 昇腾 910B 文档解析性能排查计划

## 目标与用户价值

找出同一份 PDF 在昇腾环境慢在哪一段，量化主要耗时，并交付经过同文档验证的参数组合。按 PDF 渲染、PaddleX 前处理、VLM 推理和请求调度四段取证。现场同事执行实验，由现场数据决定调参方向。

## 当前事实与约束

- 用户报告 A100 单 VLM 副本约 3 分钟，昇腾 910B 的 VLM DP4 近 30 分钟。共卡分支的 Pipeline 版面检测批量、前处理批量和 VLM 子图并发分别为 `24`、`32`、`64`。`codex/two-gpu-colocated-deployment` 分支分别为 `8`、`8`、`16`。跨平台比较须重新登记现场计时入口、实际配置和版本。
- [Ascend Compose](../../../compose.ascend.yaml) 直接运行 `vllm serve`，基础配置使用 DP3。共卡分支的环境模板选择 DP4，用户报告的现场配置也是 DP4。按 [运行配置](../../../paddleocr-server/.harness/context/runtime-and-config.md#huawei-ascend) 核对模型挂载、各 rank 的实际设备，以及副本的可见编号与设备挂载。
- 网关的默认解析入口按页发请求，FastAPI 的解析等待和 PaddleX 客户端超时配置均为 1200 秒。PaddleX 直连可提交整份 PDF，Nginx 每次分发一个完整 HTTP 请求。记录实际 URL、请求参数、并发、超时、重试和计时范围。核对 `layoutThreshold` 等请求覆盖项，避免两端识别工作量不同。见 [数据流](../../architecture/README.md)、[请求实现](../../../src/pdf_parser/clients/paddlex.py) 和 [代理配置](../../../paddleocr-server/nginx/replicas.conf.template)。
- 使用现有部署入口和测试环境。直接调用 vLLM 仅用于容器内诊断。实验中固定模型、镜像及驱动，按 [Ascend 运维指南](../../../paddleocr-server/ASCEND.md) 管理实例。测试产物写入 `output/smoke/`，临时输入和预渲染图放入 `tmp/pdfs/`。共享报告只保留页号、计数、时延、设备指标等摘要。

## 实施阶段

### 1. 建立现场基线

1. 在仓库根目录记录分支、提交、工作区状态、实际 Compose 模式、镜像 digest、模型版本或权重校验值。登记 CPU 型号、允许使用的核心及 CPU 配额、NPU 型号、驱动/CANN、PaddleX、vLLM、vLLM Ascend 和 torch-npu 版本。记录启动日志里的 dtype、注意力后端、图模式及每 rank KV cache 容量。保留白名单配置和脱敏指标摘要。
2. 检查当前服务健康和 NPU 是否有其他负载。选用原慢 PDF 作最终样本，先从中固定抽取 16–32 页，覆盖正文、复杂表格、扫描页和已知慢页。记录源文件 SHA-256 和页码。做版面批量对照时，样本至少覆盖最大候选批量。
3. 先按**原始调用方式**跑现场 DP4 基线。预热后测三次，独立记录冷启动。若 A100 可用，用相同样本、入口和请求选项补测其单副本基线。保留生产超时和重试状态，定向对照时再统一设置并单独记录。若短样本无法复现差距，扩大页集，查具体慢页、重试、主机负载和计时范围。
4. 用同一时间轴采集请求起止、状态、成功页数、输出字节和阶段耗时。记录 Pipeline NPU 及各 VLM NPU 的利用率/HBM、PaddleX 和 vLLM 的线程级 CPU，以及每个 rank 的 `running`、`waiting`、输入/输出 token、KV cache 和 preemption。有阶段直方图时，取每轮前后差值并记录样本数。以现场 `/metrics` 暴露的名称和 rank 标签为准。

现场只读命令示例。`pipeline_container`、`vlm_container` 和 `pipeline_pid` 先设置为实际 PaddleX 容器、vLLM 容器和宿主机上的 PaddleX PID。副本模式下选实际 PaddleX worker，分别采样各 worker。

```bash
git status --short --branch
npu-smi info
docker top "$pipeline_container" -eo pid,ppid,comm
docker top "$vlm_container" -eo pid,ppid,comm
docker exec "$vlm_container" curl -fsS http://127.0.0.1:8118/v1/models
docker exec "$vlm_container" curl -fsS http://127.0.0.1:8118/metrics
pidstat -t -u -w -p "$pipeline_pid" 1 60
```

用同样的 `pidstat` 命令采样 vLLM 的宿主进程。发现 CPU 饱和或利用率与核心数不符时，再核对进程允许的 CPU 列表、NUMA 绑定和容器 `cpu.stat` 中的节流增量。见 [vLLM 指标](https://docs.vllm.ai/en/v0.12.0/design/metrics/)、[Ascend CPU 绑定](https://docs.vllm.ai/projects/ascend/en/v0.18.0/developer_guide/Design_Documents/cpu_binding.html) 和 [Linux CPU 配额与统计](https://docs.kernel.org/6.5/admin-guide/cgroup-v2.html#cpu-interface-files)。

### 2. 分段定位瓶颈

| 对照 | 执行方式 | 判据 |
| --- | --- | --- |
| PDF 渲染 | 在两端实际 PaddleX 镜像里，使用同一份样本和 Serving 的 PDF 渲染函数，单独计时。再用同等像素尺寸的预渲染 PNG 对照单页 PDF，固定 `/layout-parsing` 并发和参数。 | 如果渲染秒/页差值足以解释整份文档的大部分额外耗时，且 PNG 对照差距明显缩小，优先查渲染和 CPU。用同一请求的 PNG/PDF 对照隔离渲染，分别比较渲染版本和分辨率。 |
| PaddleX 前处理 | 在 PNG 对照中，记录方向分类、UVDoc 展平、PP-DocLayoutV3 检测、裁块/合块的耗时和每页版面块数。按实际安装版本使用性能计时或短时采样。 | VLM 多数时间空闲，PaddleX 阶段耗时高时，先定位对应阶段。单个宿主线程长期接近满载支持 CPU 串行瓶颈。Pipeline NPU 忙时优先定位 CV 模型。 |
| VLM 单副本 | 两端都用 `TP=1, DP=1`，预热后从诊断客户端直接用相同正文块和表格块请求 vLLM，固定模型、图片像素、prompt、采样参数和生成上限。先测并发 1，再固定同一并发测批量。 | 在输入和输出 token 可比时，高首 token 延迟需要结合排队、视觉编码和 prefill 判断。每输出 token 耗时高，重点查 decode 和运行时。VLM 单块接近时，继续查前道和调度。 |
| DP4 调度 | 在一台 910B 上，用同样的裁块负载和端到端页集对比 `DP=1` 和 `DP=4`。DP1 选 DP4 已用的一张卡。固定 Pipeline、TP、每卡预算、镜像和入口并发。对应调整 DP 和可见设备，预热后再测。 | 各 rank 持续低 `running` 且 `waiting` 低，先查供给和批量。长期只有少数 rank 产生 token，查调度和设备映射。`waiting` 持续积压且 preemption 增长，查 KV cache。DP1 持续快于 DP4 时，再检查宿主线程竞争和 DP 开销。 |

PaddleX 3.7 的 Serving 在 PDFium 锁内逐页渲染。如果现场版本的导入路径一致，可在两个实际 Pipeline 容器中用下面的命令测渲染。`sample_pdf` 是宿主机上的抽样 PDF。输入传输和 Python 导入在计时范围外，命令只打印页数和耗时。

```bash
docker exec -i "$pipeline_container" python -c '
import sys
from time import perf_counter

from paddlex.inference.serving.infra.utils import file_to_images

sample = sys.stdin.buffer.read()
for run in range(4):
    start = perf_counter()
    pages, _ = file_to_images(sample, "PDF")
    elapsed = perf_counter() - start
    print(f"run={run} pages={len(pages)} wall_s={elapsed:.3f} s_per_page={elapsed / len(pages):.3f}")
    del pages
' < "$sample_pdf"
```

第 0 轮单独记录，使用第 1–3 轮的中位数。检查两端渲染器版本和像素尺寸。若该导入在现场版本中有变，以实际 Serving 调用的渲染函数为准。见 [PaddleX Serving 渲染实现](https://github.com/PaddlePaddle/PaddleX/blob/release/3.7/paddlex/inference/serving/infra/utils.py#L256-L300)。

### 3. 按证据逐项调参

每轮只动一个变量或一个有明确依赖关系的配置组。先复用小样本，固定请求参数、预热、样本顺序和统计范围。

| 证据 | 参数和试跑档位 | 通过条件 |
| --- | --- | --- |
| VLM 有余量，当前版面块提交受限 | 以实际 `VLRecognition.genai_config.max_concurrency` 为基线，仓库值为 `32`。先试 `48`，有收益再评估 `64`。副本模式先确认各 worker YAML 的生效值和活跃 worker 数。 | 成功页/秒提高，rank 获得更多有效工作，超时和长尾无明显恶化。`max-num-seqs=16` 时 DP4 理论共 64 个运行序列，实际受 token 预算、KV cache 和 rank 分布限制。 |
| 网关逐页发送，VLM 经常空闲 | 从现场 `PDF_PARSER_CONCURRENCY` 基线开始，若为 `1` 则试 `2`，有收益再试 `4`。保持 VLM 子块并发上限不变。若单 Pipeline 本身串行，再单独评估两个 Pipeline worker，在对照中匹配合计子块并发上限，并检查共享 Pipeline NPU 的容量。 | 确实有重叠页面，整份耗时下降。出现排队增长、超时或共享 NPU 饱和时回退。固定逐页业务可另测 `use_queues` 的 `True` 与 `False`。 |
| 多页直传，版面检测占时高 | 以 `SubModules.LayoutDetection.batch_size=32` 为仓库基线，对照 `16`，记录微批次大小与 NPU 内存。方向分类受限时再单独对照 `DocOrientationClassify.batch_size` 的 `8` 和 `16`，保持 `DocPreprocessor.batch_size=32`。 | CV 秒/页下降，端到端吞吐提升，Pipeline NPU 内存和结果质量稳定。 |
| 多页直传，实际裁块准备批次常超过 16 页且裁块耗时高 | `layout_prep_cpu_workers` 试 `16 → 32`。保持 VLM 并发和页面批量一致。 | 裁块阶段及整份文档都能重复变快。对逐页入口保持基线值。 |
| UVDoc 占时高，输入是平整电子 PDF 或平整扫描件 | 先用官方接口的 `useDocUnwarping=false` 做限定样本对照（核对现场 OpenAPI）。需要落入配置时对应 `DocPreprocessor.use_doc_unwarping`。方向分类先保持开启；图表、印章开关只在该类任务明确不需要时单独测试。 | 在业务接受的页型上，正文、表格、坐标和印章检查通过。变形扫描页和拍照件按原开关处理。 |
| VLM 有持续排队、KV cache 接近满且发生抢占 | 固定并发。若每卡 `VLM_GPU_MEMORY_UTILIZATION` 实际为 `0.3` 且有明确 HBM 余量，试 `0.4`，或单独降低并发比较。若 cache 有余量而序列数持续顶到上限，再独立测试 `VLM_MAX_NUM_SEQS`。`VLM_MAX_NUM_BATCHED_TOKENS` 仅在实测显示 token 调度预算受限时另测。 | 排队或抢占下降，成功页/秒提高，HBM 无异常，容器无 OOM 或重启。 |
| 固定裁块在 910B 的单副本仍明显慢 | 查实际图模式、dtype、注意力后端和宿主线程。按现场版本文档核对 ACLGraph、绑核、NUMA 和 CPU 配额，再做一项配置的对照。 | 能解释慢在首 token、decode 或宿主侧调度，并给出调整前后的指标。镜像或驱动变更另行评估。 |

副本入口的替换仍匹配 `max_concurrency: 16`，当前模板已经是 `32`。开展副本并发对照前，先确认生成文件确实采用候选值。表中的初值来自仓库或用户报告，现场先核对实际值。见 [Pipeline 配置](../../../paddleocr-server/.harness/context/pipeline-configuration.md#vlrecognition)。

### 4. 可调参数清单

#### 页面供给与设备拓扑

| 参数 | 初值或候选 | 何时调整 |
| --- | --- | --- |
| `PDF_PARSER_CONCURRENCY`（CLI `--concurrency`） | 默认 `1`，先试 `2`、`4` | 网关逐页发送时观察实际重叠页数。直调 PaddleX 的实验由诊断客户端控制并发。 |
| `CONTRACTLENS_PIPELINE_MODE`、`CONTRACTLENS_PIPELINE_WORKERS` | `single` 对 `replicas` 的 `2`，两副本有收益再试 `4` | 多个独立请求可以分发时评估。比较 worker 是否同时在处理，以及共用的 Pipeline NPU 和 CPU 是否出现争用。 |
| `PIPELINE_NPU_ID`、`VLM_NPU_IDS`、`VLM_DATA_PARALLEL_SIZE` | 现场 DP4 对 DP1，可进一步试 DP2 | 固定每卡预算和输入负载，核对可见实例、设备挂载和 rank 映射。设备分配用同等级空闲卡，避免 Pipeline 与 VLM 共卡。 |
| `tensor-parallel-size`、`VLM_DATA_PARALLEL_BACKEND` | `1`、`mp` | 作为拓扑控制项记录。仅当现场模型或部署需求需要 TP、或后端版本限制时单独立项验证。TP 扩展须重新核对支持范围、进程和设备映射。 |

#### Pipeline YAML 与请求开关

| 参数 | 初值或候选 | 何时调整 |
| --- | --- | --- |
| `VLRecognition.genai_config.max_concurrency` | 每 worker `64`，对照 `32`、`48` | 单独调整版面块供给。多 worker 先看有效合计在途数及生成 YAML。 |
| `use_queues` | `True` | 多页直传保留开启；逐页请求可单独对照 `False`，检查队列组批开销。 |
| 顶层 `batch_size` | `64` | 多页请求的页面采样批量。首轮保留；整段 PDF 有内存峰值时对照较小档位，例如 `32`。 |
| `SubModules.LayoutDetection.batch_size` | `24`，对照 `16`、`32` | 多页直传、版面检测成为瓶颈时测试。 |
| `SubPipelines.DocPreprocessor.batch_size`、其 `DocOrientationClassify.batch_size` | 分别为 `32`、`8`，按阶段 3 对照方向分类批量 | 先确认有足够多的页进入文档前处理。 |
| `layout_prep_cpu_workers` | `16 → 32` | 版面块准备耗时高且内部批次超过 `16` 页时测试；逐页请求走单页准备。 |
| `SubModules.VLRecognition.batch_size` | `4096` | 内部版面框批量。首轮保留；确有大批组装、内存峰值或长尾时单独测试降低上限。 |
| `use_doc_preprocessor`、`use_doc_orientation_classify`、`use_doc_unwarping` | 均为 `True`；平整件优先仅试关展平 | 前者控制整套文档前处理；后两项各自影响方向和变形校正。用 `useDocOrientationClassify`、`useDocUnwarping` 做按请求的限定样本对照。 |
| `use_chart_recognition`、`use_seal_recognition`、`use_layout_detection` | 分别为 `False`、`True`、`True` | 按业务需要逐项对照。关闭版面检测会改成整图识别，适合作为单独诊断或业务路径，结果形态与常规版面解析不同。 |
| `LayoutDetection.threshold`、`layout_nms`、`layout_unclip_ratio`、`layout_merge_bboxes_mode`、`merge_layout_blocks` | 现有分类阈值、`True`、`[1.0, 1.0]`、分类策略、`True` | 只有确认 VLM 请求因框数或裁块面积偏高时，再通过质量对照调整。网关的 `PDF_PARSER_LAYOUT_THRESHOLD` 默认 `0.5`，显式 `layoutThreshold` 优先于 YAML；`PDF_PARSER_USE_LAYOUT_DETECTION` 对应网关 `useLayoutDetection`。 |
| `minPixels`、`maxPixels`、`maxNewTokens` | PaddleX 请求项，以现场默认和自然 token 分布为基线 | 仅在超大裁块或长输出占主导时做质量对照。检查小字、印章和完整表格；压低生成上限可能截断结果。 |
| `Serving.visualize`、`returnMarkdownImages`、`outputFormats`、`restructurePages` | YAML 可视化已为 `false`；其余为请求项 | 输出编码、传输或重组耗时高时，可按业务需要关闭。PaddleX 3.7 可单独用 `returnMarkdownImages=false` 跳过 Markdown 图片编码。 |
| `format_block_content`、`markdown_ignore_labels`、`Serving.extra.max_num_input_imgs` | 当前按 YAML | 分别涉及输出格式、Markdown 内容和输入页数上限，作为结果口径记录。降低输入页数可能少处理页面，比较吞吐时核对完成页数。 |

参数名和请求支持情况以现场 OpenAPI 和 [PaddleX 3.7 接口说明](https://paddlepaddle.github.io/PaddleX/3.7/en/pipeline_usage/tutorials/ocr_pipelines/PaddleOCR-VL.html) 为准。保持原 PDF 像素尺寸和请求参数是基线的一部分；预渲染 PNG 用来隔离渲染耗时。

#### vLLM 调度、缓存与 Ascend 运行时

| 参数 | 初值或候选 | 何时调整 |
| --- | --- | --- |
| `VLM_GPU_MEMORY_UTILIZATION` → `gpu-memory-utilization` | Ascend 默认 `0.3`，有抢占且有 HBM 余量时试 `0.4` | 观察 KV cache、preemption 和每卡 HBM。 |
| `VLM_MAX_NUM_SEQS` → `max-num-seqs` | `16` 每 rank；触顶且有余量再试更大档位，例如 `24` | 容量限制确实卡在运行序列数时测试。KV cache 紧张时也可反向测试减少运行序列。 |
| `VLM_MAX_NUM_BATCHED_TOKENS` → `max-num-batched-tokens` | `16384` | 只有调度 token 预算成为瓶颈时才调。大块 prefill 拖累 decode 时也可对照降低预算，检查吞吐和首 token 延迟。 |
| `enable-prefix-caching` / `no-enable-prefix-caching`、`mm-processor-cache-gb` | 前缀缓存关闭、多模态处理器缓存 `0` | 独立做缓存命中实验。目标工作负载需要确有可复用前缀或图像；重点记录命中率、吞吐和宿主内存。 |
| `max-model-len`、`enable-chunked-prefill`、`async-scheduling` | 以现场版本和实际设置为准 | 长输入、prefill 与 decode 排队竞争，或宿主调度开销突出时评估。先确认模型与 Ascend 插件支持。上下文上限需覆盖正常图像 token 和输出长度。 |
| `compilation-config.cudagraph_mode`、`enforce-eager`、`dtype`、`kv-cache-dtype`、attention backend | 从实际启动配置和日志取值 | 同裁块单副本仍慢时，有针对性验证 ACLGraph 和算子路径。精度或缓存精度实验需确认支持并做质量对照。 |
| `additional_config.enable_cpu_binding`、容器 CPU 配额/绑核、NUMA 放置 | 以容器和现场运行时为准 | 线程级 CPU、节流或跨 NUMA 指标指向宿主瓶颈时调整。按实际版本核对 `CPU_AFFINITY_CONF`、`TASK_QUEUE_ENABLE` 等可选运行时开关，单独验证。 |

根 Ascend Compose 从环境变量展开 `vllm serve` 参数。调整后核对解析后的命令行和实际启动日志。高级选项的键名和兼容性以现场 `vllm`、`vllm-ascend` 版本为准。见 [根 Ascend Compose](../../../compose.ascend.yaml)、[vLLM 调度调优](https://docs.vllm.ai/en/stable/configuration/optimization/)、[Ascend 图模式](https://docs.vllm.ai/projects/ascend/en/v0.18.0/user_guide/feature_guide/graph_mode.html)。

#### 超时和重试口径

记录实际入口的时限。CLI 默认单次请求为 `PDF_PARSER_TIMEOUT_SECONDS`（可由 `--timeout` 覆盖），FastAPI 的解析等待和客户端超时配置、Nginx 的 `proxy_read_timeout` 均为 1200 秒。记录 `PDF_PARSER_RETRIES` 和实际后端尝试次数。定向实验可以单独测 `PDF_PARSER_RETRIES=0`。区分计算时长和等待时间，按原业务时限验收候选配置。见 [网关 API](../../../src/pdf_parser/api.py) 和 [Nginx 配置](../../../paddleocr-server/nginx/replicas.conf.template)。

## 验证与验收

- 小样本每组预热后至少测三次，报告成功页/秒中位数和波动范围、整批耗时、失败/重试数。逐页请求记录 p50 和 p95 并注明样本数，整份 PDF 提交记录文档级时长。候选收益应超出基线波动，最终用原慢 PDF 走同一入口复测基线和候选。
- 核对全部页数、页序、正文、表格和印章坐标。通过业务网关取得的结果按 [真实烟测流程](../../workflows/remote-validation.md) 验证，PaddleX 原始响应按其自身协议检查。记录空白页或模型质量问题，保留完整文档的 fail-fast 语义。
- 结果表每行记录实验 ID、样本哈希和页码、镜像/版本、变更项与生效值、入口和并发、成功页/总页、耗时、页/秒、尾延迟、阶段耗时、每 rank 指标、质量结论以及下一步。可复现的基准写入 `reports/benchmarks/`，现场运行事实写入 [远端状态](../../operations/remote-state.md)。

## 进度记录

- 2026-11-22 汇总现场反馈、仓库配置与上游实现，整理基线、分段对照和参数试跑顺序。待现场采集运行值和耗时。
- 2026-11-23 补充页面供给、Pipeline、vLLM 和请求层调参清单，记录仓库默认与现场生效值的核对方式。
- 2026-11-24 对齐当前分支的 Ascend vLLM 启动、Pipeline 批量与并发，以及 FastAPI 超时，现场数据待采集。
- 2026-11-27 共卡分支采用 `83d23bf` 的 Pipeline 和超时参数，现场数据待采集。

## 意外发现

- 基础 Compose 和共卡模板的 DP 数分别为 3 和 4。现场需记录实际模式、设备挂载、图模式和入口，再用测试结果指导后续变更。

## 决策记录

- 优先复现端到端基线，并行准备分段测量。先验证 CPU 渲染与 VLM 单副本，再用同机 DP1/DP4 对照决定是否扩并发。A100 数据作为跨平台参照，候选配置的验收以同机受控实验为依据。

## 恢复与回滚

- 实验前记下现场原配置、镜像和设备映射。发生 OOM、容器重启、持续超时或质量回归时停止加压。恢复原 YAML、环境和 Compose 选择，用根目录 `scripts/docker.sh config`、`up`、`ps` 复核，重新跑最小真实解析。
- 改动只进入批准的实验配置和窗口。保留现有工作区改动、模型缓存和原始 PDF。

## 结果总结

现场验证待执行。最终交付应包含一个有阶段计时支撑的主瓶颈判断、一组经同机对照验证的参数，以及原慢 PDF 的完整前后耗时和质量结果。
