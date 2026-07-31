---
status: active
owner: Codex
created: 2026-07-31
updated: 2026-07-31
scope:
  - src/pdf_parser/config.py
  - src/pdf_parser/clients
  - src/pdf_parser/normalization
  - src/pdf_parser/service.py
  - src/pdf_parser/models.py
  - src/pdf_parser/api.py
  - src/pdf_parser/cli.py
  - tests
  - README.md
  - docs/api.md
  - .harness/architecture
  - .harness/operations
supersedes:
  - AGENTS.md-current-pipeline-only-boundary
  - README.md-no-vlm-current-state
  - architecture-invariants-global-fail-fast-for-auxiliary-fallback
blocked_by: []
---

# 基于置信度的 VLM 元素级兜底

## 目标与用户价值

保留 PaddleX `PP-StructureV3` / `layout-parsing` 作为主解析链路，仅把置信度不足或内容为空的
疑难元素裁剪图发送给独立多模态模型复核。VLM 只能转写图像中直接可见的内容，不能根据上下文
补全、总结或新建页面元素；其输出经过严格结构和语义校验后才允许替换 PaddleX 的候选文本。

目标是提高低置信度表格和印章难例的可用性，同时满足以下边界：

- 高置信度元素不调用 VLM，不增加正常页面的生成式风险和延迟。
- VLM 不能修改候选元素的类型、坐标、阅读顺序或页面结构。
- 无法清楚辨认时显式返回“不确定/无法辨认”，不得强猜。
- PaddleX 原结果、触发依据和最终采用来源可审计；日志中不出现 Base64、完整响应或正文。

当前实施范围已收敛为印章 v1：表格因缺少内容置信度和安全接受规则而延期。印章能力由默认关闭
的开关控制，只对已检测且 OCR 文字为空、缺分数或低于配置阈值的元素生效。

## 当前事实与约束

### 本地实现

- 当前链路为 `PaddleXClient -> normalize_page() -> PageResult`。归一化直接生成最终模型，
  尚无“置信度评估 -> 候选选择 -> VLM 增强 -> 最终组装”的中间层。
- `overall_ocr_res.rec_scores` 是行级识别分数。只有页面没有版面块、完全回退到 OCR 行时，
  这些分数才被写入普通 `DocumentDetail.layout_score`。
- 页面存在 `parsing_res_list` 时，正文优先使用 `block_content`，或按 OCR 行中心点落入
  `block_bbox` 来拼接文本；匹配到的 `rec_scores` 当前会被丢弃。
- `layout_det_res.boxes[].score` 和块级 `layout_score` 表示检测/版面置信度，不能当作 OCR
  文字置信度。`layoutThreshold=0.5` 是版面检测阈值，不是 VLM 兜底阈值。
- 印章文字已经保留 `SealText.ocr_confidence`，印章版面框可以保留 `SealDetail.layout_score`。
- 当前只保留 PaddleX 元素裁剪图的名称以解析印章坐标，Base64 图像未进入模型或编排层。
  另一个 active plan `2026-07-30-element-image-resources.md` 正在设计元素图片资源，两个计划
  应共享裁剪/解码能力，但 VLM 内部临时裁剪不应依赖公共图片 URL 或持久化完成。
- 当前文档失败策略是全局 fail-fast。VLM 作为可选增强时是继续使用 PaddleX 结果还是让整份
  文档失败，属于需要显式决定的新策略。
- `2026-07-28-whole-document-submission.md` 计划会改变 PaddleX 提交粒度。置信度评估和 VLM
  增强应以“规范化后的页”为边界，不依赖 PaddleX 是逐页还是整份提交。

### 2026-07-31 远端只读/合成输入观测

- `GET http://192.168.0.67:8880/health` 返回 `errorCode=0`、`errorMsg=Healthy`。
- PaddleX OpenAPI 暴露 `/health`、`/layout-parsing`、`/restructure-pages`；
  `/layout-parsing` 的 `InferRequest` 要求 `file`，并支持当前客户端使用的
  `fileType`、`useLayoutDetection`、`layoutThreshold` 和 `visualize`。
- `GET http://192.168.0.194:8000/v1/models` 返回 `qwen3.6-27b`，任务为 `chat`，
  backend 为 `vllm`，模型列表中的运行状态是 `unknown`。
- 使用内存生成的纯红 PNG 调用
  `POST http://192.168.0.194:8000/v1/chat/completions` 成功，证明
  `qwen3.6-27b` 当前部署接受 OpenAI 风格的 `image_url` data URI。
- 同一合成图请求成功使用 `response_format.type=json_schema` 并以
  `finish_reason=stop` 返回结构化 JSON；但模型同时返回了 `status=unreadable` 和
  `observed_color=red`。这证明 JSON Schema 只能约束形状，客户端仍必须校验字段间语义。
- 一次损坏的极小 PNG 使远端返回包含内部堆栈的 500 错误。客户端错误边界必须丢弃远端完整
  body，只保留状态码、请求上下文和安全的错误分类。

上述探测没有发送仓库 PDF、图片或正文，也没有验证真实文档准确率、阈值、吞吐或最大图片
尺寸。生产阈值必须从代表性难例校准，不能从单个样例或模型自报置信度推导。

## 目标架构

```text
PaddleX 原始页
  -> 基础归一化：元素、坐标、OCR 行及原始分数
  -> 置信度证据聚合：OCR 与 layout 信号分开保存
  -> 兜底选择器：按元素类型和可配置策略产生 reason
  -> 元素图像提供器：优先可靠的 PaddleX crop，否则同坐标系本地渲染裁剪
  -> VLMClient：有界并发、严格 JSON Schema、传输重试、脱敏错误
  -> VLM 结果语义校验：不确定、截断、越权输出或结构异常均拒绝
  -> 合并器：只替换获准的内容字段，保留坐标/类型/顺序和 PaddleX 证据
  -> 重建 document_content、印章引用和最终 PageResult
```

建议将内部中间对象与公共 Pydantic 输出模型分开，避免为了编排而把 Base64、完整 OCR 响应或
临时图像暴露到 API。`service.py` 负责调用顺序和并发；PaddleX 与 VLM 各有独立客户端；
置信度聚合、触发判定、提示词/响应验证和结果合并分别保持可离线测试。

## 实施阶段

### 阶段 1：固定范围、基准和输出契约

- [x] 用户确认 v1 只处理已被 PaddleX 检测到的表格和印章；不做普通文本、标题、公式、
  图表或整页漏检审核。表格与印章分别使用响应 Schema 和验收器。
- [ ] 从 `resources/` 中选择少量普通页、模糊页、印章页和误识别页，只读建立人工标注的
  元素级 golden set。样例 JSON 只能作为候选，必须人工核对图像。
- [ ] 定义“可接受替换”：可见字符正确、没有新增不可见字符、未知片段使用统一占位符、
  坐标和元素数不变。
- [ ] 定义可选的公共审计字段，建议至少包含 `recognition_source`、
  `fallback_status`、`fallback_reason` 和 PaddleX 置信度摘要。是否保留
  `paddlex_text` 由兼容性和数据量要求决定。
- [x] VLM 失败、超时、校验失败或任何局部无法辨认时不采用 VLM 输出，保留 PaddleX。
- [x] 审计字段只能以向后兼容的可选字段增加；既有 JSON 字段、类型和嵌套结构不删除、
  不重命名，VLM 关闭或未采用时保持现有输出兼容。

可观察结果：存在经人工确认的输入/期望清单、版本化的输出契约和明确的验收指标，尚不改变
生产解析结果。

### 阶段 2：保留并聚合 PaddleX 置信度证据

- [ ] 在归一化内部保留每条 OCR 的 `text`、`rec_score`、polygon/bbox 和与版面元素的归属。
  继续遵守 `rec_texts[i]` 与同下标 `rec_scores[i]`、`rec_polys[i]` 配对的不变量。
- [ ] 普通版面块按可靠的空间关系关联 OCR 行；记录未匹配、缺分数和空文本，不用零值伪装
  缺失分数。
- [ ] OCR 与 layout 信号分开建模。每个元素计算可解释摘要，例如最小值、P10、字符加权均值、
  低分字符/行占比和有效样本数，但不把 layout score 与 OCR score 简单平均。
- [ ] 建立按元素类型配置的选择器，触发原因至少区分 `empty_text`、
  `low_ocr_confidence`、`missing_ocr_confidence`、`low_layout_confidence` 和
  `structural_validation_failed`。
- [ ] 第一轮使用 shadow 模式收集触发率和误报，不用未经校准的固定阈值覆盖结果。

需要明确的盲区：仅基于已检测元素的低分无法发现“PaddleX 完全漏掉的元素”。若要覆盖漏检，
需另加页面级审计触发器，例如非空页面却无元素、OCR 覆盖异常或整页 VLM 审核；该能力不应
隐含混入元素级 v1。

可观察结果：给定裁剪后的 PaddleX 响应字典，可以稳定解释每个元素为何触发或不触发 VLM，
缺失置信度不会被误判为高分或低分。

### 阶段 3：提供可靠的元素图像

- [ ] 实现只在内存中流转的图像对象，校验 MIME、尺寸、解码结果和最大像素数。
- [ ] 优先使用与目标元素可靠绑定的 PaddleX crop；不能只凭数组下标猜测元素与图片关系。
- [ ] crop 不存在时，按 PaddleX 页面像素尺寸渲染原 PDF/图片，再用 `layout_bbox` 加可配置
  padding 裁剪。必须验证 PDF 点坐标、渲染像素和 PaddleX 坐标的转换。
- [ ] 裁剪图只在请求体中编码为 data URI；不写日志、异常、诊断文件或最终 JSON。
- [ ] 与元素图片资源计划共享解码、坐标和 MIME 代码，但保持“内部临时 crop”和“公共持久化
  资源”两个生命周期。

可观察结果：测试可证明传给 VLM 的图像只覆盖目标元素及固定边距，坐标不越界，损坏图像在
发请求前被拒绝。

### 阶段 4：实现独立 VLM 客户端和护栏

- [ ] 增加独立 `VLMClient`，使用异步 `httpx` 调用 OpenAI 兼容
  `/v1/chat/completions`。配置至少包含 enabled、endpoint、model、timeout、retries、
  concurrency、max fallback elements 和 trust_env。
- [ ] `/v1/models` 只用于健康/能力检查，不在每次解析时调用。业务请求固定使用经确认的
  `qwen3.6-27b` 模型 ID。
- [ ] 仅对传输错误、超时和明确可重试状态重试；不在异常中透传远端 body、图片、提示词或正文。
- [ ] 每种元素类型使用独立严格 JSON Schema。文本类建议返回：
  `status=readable|partially_readable|unreadable`、`text` 和 `unknown_count`。
- [ ] 系统提示词明确要求：只转写裁剪图中直接可见内容；禁止补全、纠错、解释、总结和利用文档
  常识；看不清的连续片段写统一占位符；完全看不清时 `text=null`；不要输出候选框或新增元素。
- [ ] 默认不把 PaddleX 文本发给 VLM，避免错误 OCR 对模型产生锚定；只提供元素类型、转写规则
  和图像。若 A/B 证明候选文本能提升准确率且不增加脑补，再单独决策。
- [ ] 使用 `temperature=0`、类型相关 token 上限和严格 Schema，但不把这些参数视为防幻觉的
  充分条件。
- [ ] 客户端进一步执行语义校验：`unreadable` 必须配 `text=null`；partial 必须包含占位符；
  `finish_reason` 非 `stop`、字段矛盾、超长输出、非法 HTML/公式或越权字段全部拒绝。
- [ ] 不使用 VLM 自报置信度决定是否采用结果；采用与否只基于可验证结构、业务规则和评测策略。

可观察结果：损坏图片、500、超时、截断、拒答、非法 JSON、合法但语义矛盾和完全无法辨认都
有离线测试，并且不会覆盖 PaddleX 内容。

### 阶段 5：编排、合并和公共输出

- [ ] `service.py` 先完成 PaddleX 页面归一化，再按页和元素产生有界的 VLM 任务；VLM 并发与
  PaddleX 并发独立，设置每页/每文档调用上限，防止低质量文档造成请求风暴。
- [ ] 合并器只允许修改目标元素的可转写内容；`layout_label`、mapped type、bbox、position、
  order、page_num、seal_id 和 content reference 关联保持不变。
- [ ] 只有 `readable` 或满足验收规则的 `partially_readable` 才能替换；`unreadable`、失败或
  校验拒绝按用户确认的策略保留 PaddleX 或使文档失败。
- [ ] 合并后统一重建 `document_content` 和 `content_references`，避免正文与元素详情不一致。
- [ ] 公共输出显式标记来源和状态；若 VLM 未启用，默认输出与现有契约保持一致。
- [ ] CLI/API 暴露必要的启用方式和健康信息，不把内部提示词或图片加入响应。
- [ ] 重新核算 API 整体超时：PaddleX 超时、VLM 单次超时、最大调用数和并发必须形成可证明的
  上界。

可观察结果：高分元素零 VLM 调用；低分元素仅在校验通过时改变内容；输出页序、坐标、印章
引用和 fail-fast/soft-fail 行为符合已确认契约。

### 阶段 6：评测、灰度和文档

- [ ] 先以 shadow 模式运行代表性文档：记录元素类型、分数摘要、触发原因、耗时、token 数和
  “是否会采用”，不记录图片或正文。
- [ ] 人工对比 PaddleX、VLM 与 golden set，统计触发召回率、有效纠正率、错误覆盖率、凭空
  新增字符率、fallback 率以及 P50/P95 延迟。
- [ ] 按元素类型选阈值，避免全局单阈值。只有达到用户确认的错误覆盖和脑补上限后才启用写入。
- [ ] 真实烟测只写 `output/smoke/`；验证 VLM 不可用、慢响应和部分元素不可辨认的路径。
- [ ] 更新 README、API 文档、架构边界、不变量、远端状态和 `.env.template`。若决定改变
  辅助 VLM 的失败策略，在不变量中明确 PaddleX 主链路失败与 VLM 增强失败的区别。
- [ ] 运行定向测试、`& .\.harness\scripts\check.ps1`、真实烟测；部署时再遵循 T4 远端部署
  工作流。

可观察结果：有带人工结论的准确率/幻觉率/延迟报告、可回滚的功能开关和完成的仓库门槛证据。

## 配置草案

以下名称是计划建议，不是已实现事实：

```text
PDF_PARSER_ENDPOINT=http://192.168.0.67:8880
PDF_PARSER_VLM_ENABLED=false
PDF_PARSER_VLM_ENDPOINT=http://192.168.0.194:8000
PDF_PARSER_VLM_MODEL=qwen3.6-27b
PDF_PARSER_VLM_TIMEOUT_SECONDS=30
PDF_PARSER_VLM_MAX_ATTEMPTS=5
PDF_PARSER_VLM_CONCURRENCY=<待确认>
PDF_PARSER_VLM_MAX_ELEMENTS_PER_PAGE=<待确认>
PDF_PARSER_VLM_MAX_ELEMENTS_PER_DOCUMENT=<待确认>
PDF_PARSER_VLM_SHADOW_MODE=true
```

置信度阈值应支持按元素类型配置。配置中要区分 OCR 识别阈值和 layout 检测阈值，避免继续复用
含义模糊的 `threshold` 名称。生产默认保持 VLM 关闭，直到 golden set 校准和灰度验收完成。

## 验证与验收

### 离线测试

- 配置：VLM 默认关闭、环境变量校验、endpoint/model/阈值/上限边界。
- 置信度：混合高低分、缺分数、空文本、OCR 行与块空间匹配、印章多文本和精确阈值边界。
- 客户端：请求 Schema、图像 MIME/解码、重试分类、超时、HTTP 错误脱敏和 `finish_reason`。
- 护栏：非法 JSON、Schema 违规、字段语义矛盾、拒答、截断、超长输出和未知占位符。
- 编排：高分不调用、低分调用一次、调用上限、独立并发、页序、进度和已确认失败策略。
- 合并：只改文本、保留坐标/类型/顺序、重建正文和印章引用、保留审计来源。
- API/CLI：同步接口总超时、错误映射、VLM 开关和向后兼容输出。

### 远端验收

- 再次检查 PaddleX `/health`、VLM `/v1/models` 和合成图结构化输出。
- 对用户选定难例运行 PaddleX 基线、VLM shadow 和启用合并三组比较。
- 评估至少包含：PaddleX 基线准确率、有效纠正率、错误覆盖率、凭空新增字符率、fallback
  调用率、每文档 VLM 调用数、P50/P95 延迟和失败降级结果。
- 不把一次服务状态、单个阈值或单文档结果固化为永久事实。

### 建议的上线门槛

- golden set 中没有被自动接受的凭空新增字符；任何新增案例先进入拒绝或人工复核路径。
- 已确认类型的有效纠正率和错误覆盖率达到用户给定目标。
- VLM 关闭时输出与现有回归样例兼容。
- 达到调用数和 P95 延迟预算，VLM 500/超时不会产生伪成功或静默错误覆盖。
- `& .\.harness\scripts\check.ps1` 通过，真实烟测证据和未验证风险已记录。

## 已确认决策与延期项

用户于 2026-07-31 确认：

1. v1 只处理已检测到但低置信度的表格和印章，不处理完全漏检元素。
2. VLM 失败、超时、校验失败或有任一部分无法辨认时，保留 PaddleX 原结果。
3. 只要存在任何无法辨认部分，VLM 内容字段必须为 `null`，不接受部分结果。
4. 可增加向后兼容的可选审计字段，但不删除、改名或改变既有 JSON 字段及嵌套结构。
5. 初始设想为单次超时 30 秒、最多总尝试 5 次。
6. PaddleX 代码默认地址改为 `http://192.168.0.67:8880`，部署环境暂不调整。
7. 元素裁剪只在内存中使用，不持久化为业务数据，也不记录图片或正文日志。
8. 当前先验证路线可行性，不确定生产阈值和正式人工真值集。

2026-07-31 可行性实验表明，30 秒适合印章但不适合完整表格；5 次表格重试会使单元素等待
超过 160 秒。模型还会在遮挡内容上错误返回 `readable` 并补齐不可见值。因此表格兜底仍被以下
两项阻塞，但不再阻塞印章 v1：

- PaddleX 当前不提供表格内容/cell 置信度，只有不能代表内容正确性的 layout score。
- 尚无能在无人工真值时安全接受 VLM 整表/整章输出的规则。

详细证据见
[`../../reports/investigations/2026-07-31-vlm-fallback-feasibility.md`](../../reports/investigations/2026-07-31-vlm-fallback-feasibility.md)。
表格继续保持未实现；印章采用原图/红色隔离图一致性校验，任一不可读或不一致均保留 PaddleX。

## 进度记录

- 2026-07-31 — 阅读架构、不变量、变更工作流、计划约定和远端状态；检查实现、测试及两个
  相关 active plan。
- 2026-07-31 — 只读确认 PaddleX 健康和 OpenAPI 摘要；确认 VLM 模型列表。
- 2026-07-31 — 用内存合成图片确认 `qwen3.6-27b` 的图像输入和 JSON Schema 能力；记录损坏
  图片错误泄露内部堆栈及合法 JSON 的语义矛盾。
- 2026-07-31 — 建立本计划；实现被用户决策和真实难例校准阻塞。
- 2026-07-31 — 用户确认表格/印章范围、soft-fail、任一局部不清即 `null`、向后兼容审计
  字段、30 秒单次超时、最多 5 次尝试、PaddleX 新默认地址和不留存裁剪。
- 2026-07-31 — 完成通用表格真实样本可行性调查。技术链路可通且高分辨率 VLM 偶有局部
  纠错，但整表/印章结果会脑补且不稳定；30 秒表格超时不足，自动覆盖暂不具备上线条件。
- 2026-07-31 — 用户决定先实现印章兜底；创建 codex/seal-vlm-fallback 分支，完成配置、双视图 VLM 客户端、软降级合并器及定向测试。
- 2026-07-31 — 全量 63 项离线测试通过；真实单页样本中 1 枚印章被一致性校验接受、1 枚因结果不一致保留 PaddleX；VLM 不可用烟测中 2 枚均软降级并通过输出契约验证。

## 意外发现

- 当前普通版面块会丢失与正文相关的 OCR 行分数，不能直接在最终 JSON 上可靠判断低置信度。
- OpenAPI 中 `layoutThreshold` 同时接受数字或对象；它仍属于版面检测参数，不应复用为 OCR
  或 VLM 触发阈值。
- 模型可以满足严格 JSON 形状但违反字段间语义，提示词护栏必须配合程序化校验。
- VLM 网关当前会把下游内部堆栈放进错误响应，客户端必须主动脱敏。
- 只看低置信度不能发现未被 PaddleX 检测到的元素，页面级漏检需要单独策略。

## 决策记录

- 决策：PaddleX 保持主解析器，VLM 只接收选中的元素图像并且不能改布局。
  理由：限制生成式模型的作用域，保留确定性的坐标、顺序和引用不变量。
  日期：2026-07-31。
- 决策：OCR 与 layout 分数分开保存和校准，不构造无解释性的统一平均分。
  理由：两者含义、缺失模式和适用元素不同。
  日期：2026-07-31。
- 决策：生产阈值不在计划阶段拍脑袋指定，先 shadow、人工核对再按元素类型选择。
  理由：远端历史只证明某些字段存在，不证明任何阈值对所有文档最优。
  日期：2026-07-31。
- 决策：严格 JSON Schema 之外必须有客户端语义校验，且不采用模型自报置信度。
  理由：合成图实测已经出现结构合法但语义冲突的返回。
  日期：2026-07-31。

## 恢复与回滚

- 所有新行为由 `VLM_ENABLED` 总开关控制；关闭后只走 PaddleX。
- 新公共字段保持可选，避免旧调用方在关闭 VLM 时发生结构变化。
- 合并前始终保留内部 PaddleX 候选；VLM 结果校验失败可按已确认策略恢复候选。
- 不修改、移动或覆盖 `resources/`。评测输出只写 `output/smoke/`，临时渲染写 `tmp/pdfs/`。
- 若实现中断，从本计划的阶段和进度记录恢复；只撤销本任务文件，不清理用户工作区。

## 结果总结

印章 v1 已完成实现与本地/真实烟测：默认关闭、低 OCR 置信度触发、双视图一致才替换、任何失败软降级。表格兜底延期。
