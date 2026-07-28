# AGENTS.md

本文件适用于整个项目根目录及其所有子目录。后续自动化开发工具在修改代码前应先阅读本文件。

## 0. 智能体 Harness 导航

本项目的智能体编程 harness 位于 [`.harness/`](.harness/README.md)。`AGENTS.md` 是 Codex
自动发现的持久化入口，`.harness/` 是项目内部的结构化知识和可执行反馈层。

- 开始代码修改前，先阅读 `.harness/README.md`，再按任务类型读取其中链接的文档。
- 涉及模块边界或数据流时，阅读 `.harness/ARCHITECTURE.md`。
- 实现、修复、重构或评审时，遵循 `.harness/WORKFLOW.md`。
- 跨模块、协议变更或多阶段任务，使用 `.harness/PLANS.md` 创建执行计划。
- 本地验证优先运行 `.harness/scripts/check.ps1`；真实烟测使用 `.harness/scripts/smoke.ps1`。

若 `.harness/` 与本文件冲突，以本文件为准；用户当前任务中的明确要求优先级更高。

## 1. 项目目标与边界

本项目是一个基于远端 PaddleX `PP-StructureV3` / `layout-parsing` Pipeline 的 PDF 文档解析客户端。

当前处理链路：

```text
PDF
  -> 本地逐页拆分
  -> 远端 POST /layout-parsing
  -> PaddleX 文档预处理、版面、OCR、表格、印章、公式、图表识别
  -> 本地结果归一化
  -> 兼容现有样例的 *_result.json
```

必须遵守以下产品边界：

- 当前版本只使用 PaddleX Pipeline 模式。
- 未经用户明确要求，不得引入 VLM、多模态大模型或外部 LLM。
- 模型推理在远端服务器完成，本项目只负责 PDF 拆页、HTTP 调用、结果归一化和 JSON 输出。
- 根目录现有 PDF、图片和 `*_result.json` 是用户样本或参考结果，不是可随意修改的测试夹具。
- 不要把样例 JSON 当作绝对真值；其中可能包含 OCR 错字、坐标系差异或模型幻觉。

## 2. 开发环境

- 操作系统：Windows，命令示例使用 PowerShell。
- Python：`>=3.11`。
- 包和虚拟环境管理：`uv`。
- 默认 PaddleX 地址：`http://192.168.0.194:8080`。
- 默认关闭 `httpx` 的系统代理继承，避免内网地址被发送到 `HTTP_PROXY`。

不要直接使用系统 `pip`。安装或更新依赖应使用：

```powershell
uv add <package>
uv add --dev <package>
uv sync
```

常用验证命令：

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pytest --basetemp .pytest-tmp
uv run pdf-parser --help
uv run pdf-parser health
```

真实 PDF 烟测应显式写到 `output/smoke/`，不要覆盖根目录样例：

```powershell
uv run pdf-parser parse "path\to\input.pdf" `
  -o "output\smoke\input_result.json" `
  --timeout 180
```

## 3. 项目结构与职责

```text
src/pdf_parser/
├── __init__.py
├── cli.py                       # Typer CLI、参数、进度和 JSON 文件写入
├── config.py                    # Pydantic Settings 和 PDF_PARSER_* 环境变量
├── errors.py                    # 面向用户的领域异常
├── models.py                    # 归一化结果和兼容 JSON 的 Pydantic 模型
├── service.py                   # 文档级编排、并发批次、页序恢复
├── clients/
│   └── paddlex.py               # /health、/layout-parsing、重试和协议校验
├── ingestion/
│   └── pdf.py                   # 使用 pypdf 拆成独立的单页 PDF
└── normalization/
    ├── paddlex.py               # PaddleX prunedResult -> PageResult
    └── seal.py                  # 印章区域匹配、坐标转换、编号和正文引用

tests/
├── test_cli.py                  # CLI 参数、默认输出路径和文件写入
├── test_client.py               # HTTP 请求和错误响应
├── test_ingestion.py            # 单页拆分有效性
├── test_normalization.py        # 版面块、表格 OCR 回退和坐标
└── test_service.py              # 多页顺序、并发批次和进度
```

修改位置约定：

- CLI 参数、终端输出、输出文件命名：修改 `cli.py`。
- 默认地址、超时、重试、并发和代理：修改 `config.py`。
- PaddleX 请求字段、重试或响应协议：修改 `clients/paddlex.py`。
- PDF 拆页、加密或损坏文件处理：修改 `ingestion/pdf.py`。
- 页级并发、失败策略、文档编排：修改 `service.py`。
- 字段映射、阅读顺序和表格处理：修改 `normalization/paddlex.py`。
- 印章区域匹配、局部坐标转整页坐标、编号和正文引用：修改 `normalization/seal.py`。
- 最终 JSON 字段：修改 `models.py`，同时更新 README 和相关测试。

不要把 HTTP、PDF、归一化和 CLI 逻辑重新混入同一个模块。

## 4. 核心行为约束

### 4.1 PDF 拆页

- 输入 PDF 必须在本地逐页拆成独立、可读取的单页 PDF。
- 这样做是为了避免远端默认页数限制，并能准确报告失败页码。
- 页码统一使用从 1 开始的编号。
- 并发处理必须有界；当前按 `Settings.concurrency` 分批，不应一次把整份长文档全部并发提交。
- 输出必须按 `page_num` 排序，不能依赖异步请求完成顺序。

### 4.2 PaddleX 请求契约

当前每页请求至少包含：

```json
{
  "file": "<single-page PDF base64>",
  "fileType": 0,
  "visualize": false,
  "logId": "pdf-parser-page-<page_num>"
}
```

约束：

- `fileType=0` 表示 PDF，不能省略，因为纯 Base64 无法自动推断文件类型。
- `visualize=false` 用于关闭常规可视化输出，但当前服务的 `markdown.images` 仍可能包含表格和印章裁剪图的 Base64。
- 印章归一化只读取 `markdown.images` 的键来提取实际裁剪框，不解码、不持久化也不记录对应的 Base64 值。
- 成功响应必须满足 HTTP 200、`errorCode == 0`，且单页请求恰好返回一个 `layoutParsingResults`。
- 传输错误和超时可以重试；明确的模型参数错误或业务错误不要盲目重试。
- 错误信息必须包含页码，并转换为 `PaddleXError`。
- 不要在日志或异常中输出 PDF Base64、完整原始响应或敏感文档正文。

### 4.3 结果归一化

主要读取：

- `prunedResult.width`、`height`
- `prunedResult.parsing_res_list`
- `prunedResult.overall_ocr_res`
- `prunedResult.seal_res_list`
- `prunedResult.layout_det_res.boxes` 中的整页印章区域
- `markdown.images` 中印章裁剪图键携带的实际整数裁剪框
- `markdown.text` 作为最终兜底

当前标签映射包括：

- `doc_title` / `title` -> `Title`
- `paragraph_title` / `section_header` -> `Section-header`
- `table` -> `Table`
- `image` / `figure` / `chart` -> `Picture`
- `formula` -> `Formula`
- `seal` -> `Seal`
- 其余默认映射为 `Text`

归一化规则：

- 优先使用 `parsing_res_list.block_content`。
- 如果版面块内容为空，则用块边界框内的 `overall_ocr_res` 行补齐。
- 如果没有版面块，则从整体 OCR 行构造文本块。
- 如果仍没有正文，最后使用 `markdown.text`。
- `rec_boxes` 为空时允许从 `rec_polys` 推导边界框。
- 每枚物理印章输出一个独立 `Seal` 详情；同一印章识别出的多段文字放入 `texts[]`，不得把文字片段误当成多枚印章。
- 印章 `rec_polys` 是裁剪图局部坐标，必须加上实际 `crop_bbox` 左上角偏移后才能写入整页 `position` 和 `layout_bbox`。
- 裁剪框来源优先级：`seal_res_list[].crop_bbox`（服务端未来直接提供）-> `markdown.images` 印章裁剪图键 -> `layout_det_res` 印章框。
- 多枚印章先保持识别结果与裁剪框的原始对应，再按页面从上到下、从左到右编号为 `page-<页码>-seal-<序号>`。
- 印章区域与识别结果数量不一致时，不得把局部坐标冒充整页坐标；保留文字和引用，但坐标留空。
- `document_content` 使用 `[印章N]`，并通过 `content_references.target_id` 精确关联 `seal_id`。
- 印章文本尚未实现语义纠错或短噪声过滤；同一文字可能出现在不同物理印章中，不得跨印章去重。
- `image_width`、`image_height`、`layout_bbox` 和 `position` 必须处于同一 PaddleX 页面像素坐标系。

#### 4.3.1 印章坐标和引用契约

PaddleX 的印章结果包含两个坐标空间：

- `layout_det_res.boxes[label=seal].coordinate` 是预处理后整页图像上的印章区域。
- `seal_res_list[].rec_polys` / `rec_boxes` 是印章裁剪图内部的局部文字坐标，不能直接写入最终页面坐标。

当前远端服务尚未在 `seal_res_list[]` 中直接返回实际 `crop_bbox`。现阶段 `normalization/seal.py` 从形如 `imgs/img_in_seal_box_<x0>_<y0>_<x1>_<y1>.jpg` 的 `markdown.images` 键提取实际整数裁剪框；如果服务端以后直接增加 `crop_bbox`，必须优先使用服务端字段。

局部 polygon 转换为整页 polygon 的唯一正确公式是：

```text
page_x = local_x + crop_bbox.x0
page_y = local_y + crop_bbox.y0
```

必须转换 polygon 的每一个点，再用全局点的 `min/max` 计算文字的 `layout_bbox`。禁止只移动部分点，也禁止把整枚印章的区域框当成文字框。

印章 OCR 数组按以下方式对应：

```text
rec_texts[i]  <-> rec_scores[i] <-> rec_polys[i]
```

- `rec_polys` 不存在时才回退到同下标的 `rec_boxes`。
- 不得用 `dt_polys[i]` 与 `rec_texts[i]` 配对；检测候选可能被识别阈值过滤，二者数量可以不同。本次真实响应中 `dt_polys=3`、`rec_texts=2`、`rec_polys=2`。
- 一枚物理印章对应一个 `seal_res_list[]` / `SealDetail`；其中多段 OCR 文字对应 `SealDetail.texts[]`，不是多枚印章。

多个印章的处理顺序必须是：

1. 先按 PaddleX 原始顺序把每个 `seal_res_list[]` 与对应裁剪框绑定。
2. 只有绑定完成后，才按 `(y0, x0)` 从上到下、从左到右排序。
3. 排序后生成 `seal_index`、`seal_id=page-<页码>-seal-<序号>` 和 `[印章N]`。
4. 裁剪框数量与印章结果数量不一致时不得猜测或直接 `zip()`；保留文字，但 `seal_region_bbox`、文字 `position` 和 `layout_bbox` 必须为空。

最终输出字段语义：

- `SealDetail.layout_bbox` / `seal_region_bbox`：整枚物理印章在页面上的区域。
- `SealDetail.position`：整枚印章区域的矩形 polygon。
- `SealDetail.texts[].position`：该文字在页面上的完整全局 polygon。
- `SealDetail.texts[].layout_bbox`：该全局 polygon 的外接矩形。
- `coordinate_space` 固定为 `page_pixels_top_left`，原点在预处理后页面左上角。
- `reference_token` 是用户可读的 `[印章N]`；机器关联必须使用稳定的 `seal_id`。
- `content_references[].target_id` 必须等于对应的 `seal_id`。
- `start_offset` 为 token 起始字符下标，`end_offset` 为 Python 切片语义的右开下标；必须满足 `document_content[start_offset:end_offset] == token`。

不要依赖 `document_details` 数组下标关联正文与印章，也不要把 `[印章内容]` 这种没有 ID 的普通文本当作引用关系。

### 4.4 输出契约

顶层结构必须保持：

```json
{
  "code": "success",
  "message": "",
  "tips": null,
  "data": {
    "task_id": "",
    "file_url": "",
    "status": 4,
    "message": "",
    "doc_recognize_result": [],
    "aigc": {
      "Label": "AIGCLabelType.AI_GENERATED",
      "ProcessingTypes": ["ocr"]
    }
  }
}
```

每页至少包含：

- `page_num`
- `document_content`
- `image_width`
- `image_height`
- `document_details`
- `content_references`
- `parse_time`

修改输出字段前必须检查现有样例和下游兼容性，不得无理由重命名或删除字段。

## 5. 远端 Pipeline 状态

远端能力是可变的，不要只根据仓库文档假设服务配置。每次涉及服务参数或模型行为时应先检查：

```powershell
uv run pdf-parser health
```

必要时读取 `/openapi.json`，并从一次真实响应的 `prunedResult.model_settings` 和印章 `text_det_params` 确认运行参数。

截至 2026-07-22，最近一次在线验证结果为：

- `use_doc_preprocessor: true`
- `use_seal_recognition: true`
- `use_table_recognition: true`
- `use_formula_recognition: true`
- `use_chart_recognition: true`
- `use_region_detection: true`
- 印章检测 `thresh: 0.3`
- 印章检测 `box_thresh: 0.65`
- 印章识别 `score_thresh: 0.5`

这些值属于远端运行状态，不是本仓库配置。服务器重启、换 YAML 或换模型后必须重新验证。

已知表现：

- 表格可以返回包含 `rowspan` / `colspan` 的 HTML。
- 调整后的印章参数能把样例中的“育限公司”纠正为“有限公司”，并过滤低置信度 `cl`。
- 高置信度短噪声 `41` 仍可能保留，不能仅靠提高识别阈值解决。
- 后续若实现短噪声过滤，应放在归一化层并做成可配置规则；必须保留较长印章编号和统一社会信用代码。
- 服务重启后的首次推理可能有模型冷启动延迟，性能测试应区分冷启动和预热结果。

印章坐标真实烟测基准（2026-07-22，模型或服务配置变化后允许有少量像素差异）：

- 输入：`resources/4-4通用表格/2大洋信息技术有限公司_商务_7.投标人信息表.pdf`
- 页面尺寸：`1191 x 1684`
- 整枚印章区域：`[620, 1, 850, 198]`
- “大洋信息技术有限公司”全局文字框：`[629, 1, 844, 182]`
- `41` 全局文字框：`[656, 174, 679, 193]`
- 两个文字框必须位于页面范围内并与整枚印章区域相交；不得退化回错误的局部框 `[9, 0, 224, 181]`。

## 6. 错误与失败策略

- 当前采用 fail-fast：任意页面失败时，整份文档解析失败，不写入伪装成成功的部分结果。
- 不要静默吞掉页面错误。
- 不要在失败后输出 `code=success`。
- 断点续跑、部分成功和错误页占位尚未实现；加入这些能力前需要先设计新的状态和输出契约。
- 加密 PDF、空 PDF、损坏 PDF 必须抛出 `InvalidPdfError`。

## 7. 编码和代码规范

- 所有源码、Markdown 和 JSON 使用 UTF-8。
- 不要因为 PowerShell 控制台出现乱码就把中文源文件转换成 GBK；应使用 UTF-8 方式读取检查。
- 保持 Python 3.11 兼容。
- 公共边界使用类型标注；数据结构优先使用 Pydantic 模型。
- 网络代码保持异步，阻塞 PDF 拆页逻辑不要混入 HTTP 客户端。
- 用户可见错误使用清晰中文，内部类名和函数名使用英文。
- 新依赖必须有明确必要性；优先使用现有依赖和标准库。
- 用户可见行为发生变化时同步更新 README。

## 8. 测试要求

默认测试不能依赖真实远端服务：

- HTTP 使用 `respx` 模拟。
- PDF 测试在临时目录动态创建最小 PDF。
- 归一化测试使用裁剪后的响应字典，不保存大体积真实响应。
- 异步测试使用 `pytest-asyncio`。

以下改动必须配套测试：

- 请求字段或错误处理：更新 `test_client.py`。
- 拆页和 PDF 校验：更新 `test_ingestion.py`。
- 标签映射、表格回退、印章过滤或坐标：更新 `test_normalization.py`。
- 并发、页序、进度、部分失败策略：更新 `test_service.py`。
- CLI 参数或输出路径：新增或更新 CLI 测试。

印章坐标改动至少覆盖：

- 优先使用服务端显式 `crop_bbox`（该字段接入后）。
- 从 `markdown.images` 键提取实际整数裁剪框并转换 polygon。
- 没有 Markdown 裁剪框时回退到 `layout_det_res`，并使用与服务端裁剪一致的整数化规则。
- 多印章保持识别结果与区域绑定，然后按视觉顺序编号。
- `rec_polys` 为空时回退 `rec_boxes`。
- 印章区域与识别结果数量不一致时不输出伪全局坐标。
- `content_references` 的 token、字符偏移和 `seal_id` 引用一致。

交付前至少运行：

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pytest --basetemp .pytest-tmp
```

远端可用且改动涉及协议或归一化时，再运行一次一页 PDF 烟测，并检查：

- 输出 JSON 可以被解析。
- 页数与输入一致。
- `document_content` 非空。
- 坐标不超出页面像素范围。
- 表格 HTML 没有被转义或截断。
- 印章文字、`seal_id` 和正文引用符合预期。
- 印章 `seal_region_bbox` 与文字全局坐标均在页面范围内，且文字框与印章区域相交。

## 9. 数据和文件安全

- 不修改、不重命名、不删除根目录用户样本，除非用户明确要求。
- 生成结果默认放到 `output/`；诊断结果放到 `output/smoke/`。
- 临时 PDF 或渲染图片放到 `tmp/pdfs/`，完成后清理。
- 不提交 `.venv/`、临时目录、大体积 Base64 响应或用户文档副本。
- 自动测试不得覆盖现有 `*_result.json`。
- 修改前先检查工作区现状，保留与当前任务无关的用户改动。

## 10. 后续扩展原则

推荐的扩展顺序：

1. 可配置的印章短噪声过滤和测试集。
2. 原始 PaddleX 响应的可选诊断摘要，不保存 Base64 图像。
3. 断点续跑和部分失败状态设计。
4. 更完整的表格、公式和图表输出契约。
5. 批量目录输入和任务级报告。

VLM 兜底不属于当前范围。只有用户明确要求并确定输入、输出、成本和失败策略后，才可以作为独立客户端和路由层加入；不得直接耦合进现有 PaddleX 客户端或归一化模块。
