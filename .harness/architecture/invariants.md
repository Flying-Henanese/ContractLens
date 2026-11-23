# Stable System Invariants

本文件只记录跨模块、必须长期保持的行为。具体请求粒度等正在迁移的行为，以当前实现、测试和 active plan 共同判断，不在此重复固化。

## 仓库与部署边界

1. `src/pdf_parser/` 与 `paddleocr-server/` 是同一仓库中的两个逻辑模块，不再作为两个独立项目
   分别部署；它们仍保留各自的运行时依赖、模型/硬件配置和职责边界。
2. 根目录 `compose.yaml` 或 `compose.ascend.yaml` 必须将 `api`、`paddleocr-vl-api` 和
   `paddleocr-vlm-server` 作为一套生命周期管理；`scripts/docker.sh` 是该整套服务唯一受支持的
   生命周期入口。
3. 统一 Compose 中，网关只能通过 `http://paddleocr-vl-api:8080` 调用 PaddleX Pipeline，不得
   直接调用 vLLM、宿主机端口或历史远端 IP。独立运行网关时才通过 `PDF_PARSER_ENDPOINT` 明确指定
   可访问的 PaddleX 地址。
4. 根 Compose 和 overlay 负责设备映射及推理容器编排。Pipeline 和 vLLM 从只读挂载的
   `paddleocr-server/` 读取其入口和配置，网关模块不得复制或改变这些配置。

## 输入、编排与失败

1. PDF 输入在本地校验。无法以空密码解密、无页面或读取时报错时抛出 `InvalidPdfError`。
   `service.py::_count_pages()` 和 `ingestion/pdf.py::iter_pdf_pages()` 均读取并校验文件。
2. 图像文档只接受 BMP、JPEG、PNG、TIFF 和 WEBP。API 要求扩展名匹配 Content-Type，
   并独立检查二进制签名是否属于支持的格式；当前签名识别结果不与扩展名交叉比对。
   `service.py::parse_image()` 再次读取并校验签名，失败抛出 `InvalidImageError`。
3. 页码从 1 开始，最终输出按 `page_num` 排序且页码唯一；图像固定归一化为第 1 页。
4. 每个单页 PDF 或图像远端请求必须恰好返回一个 `layoutParsingResults` 条目；服务为每个本地页生成一个
   归一化页面，因此最终页数与本地页数一致。
5. 当前采用 fail-fast：任一输入、远端或归一化失败导致整份文档失败，不写伪成功结果。

## PaddleX 边界

1. PDF 请求显式包含 `fileType=0`；图像请求显式包含 `fileType=1`。两者都包含
   `visualize=false`、`useLayoutDetection`（默认 `true`）和可配置的 `layoutThreshold`。
2. 成功响应必须满足 HTTP 200、`errorCode == 0` 和预期的 `layoutParsingResults` 形状。
   当前客户端检查顶层 JSON 对象和返回页数；嵌套数据类型由后续处理消费，缺少完整的协议校验。
3. 传输错误和超时可以重试；明确业务错误不盲目重试。
4. 错误应包含可定位的图像、文档或页码上下文，并遵循根 AGENTS.md 的脱敏要求。
   当前客户端透传上游业务错误的 `errorMsg`，未对该字段单独脱敏。
5. 远端启用能力和模型阈值属于运行观测，不得硬编码成客户端永久事实。

## 归一化与坐标

1. 存在版面块时，每个非印章块先使用 `block_content`/`text`，为空且 bbox 有效时使用中心点
   落在块内的整体 OCR；块外 OCR 不追加到正文。没有非印章版面详情时，整体 OCR 生成
   文本详情，包括仅有印章版面块的页面。完成印章处理后的正文仍为空时回退 Markdown 文本。
2. 有印章识别结果时，每个有效结果生成一个 `SealDetail`。缺少识别结果时，优先使用
   `layout_det_res` 中的印章检测框，无有效检测框时回退到 `parsing_res_list` 的
   印章块。每个区域生成一个 `SealDetail`、ID 和引用，`texts=[]`。重复结果或区域会保留。
3. 印章 `rec_texts[i]` 与同下标的 `rec_scores[i]`、`rec_polys[i]` 配对。同下标的
   polygon 缺失或无效时回退到 `rec_boxes[i]`。`dt_polys` 不参与配对。
4. 印章局部 polygon 只有取得可靠 `crop_bbox` 后才能逐点平移到页面坐标：`page_x = local_x + crop_bbox.x0`，`page_y = local_y + crop_bbox.y0`。
5. 每枚印章独立按服务端显式 `crop_bbox`、Markdown 图片键、版面检测印章框的顺序选择裁剪框；后两种来源只有在区域数量与识别结果数量一致时才能按原始下标绑定。
6. 多印章先按原始顺序绑定结果与区域；拥有显式裁剪框的条目独立保留该框，其余条目只有在
   Markdown 或版面区域总数与识别结果总数一致时才按原始下标绑定。全部条目取得区域后再按
   `(y0, x0)` 视觉排序编号；未取得可靠区域的条目仍保留文字和引用，但该条目的区域及文字
   坐标留空。
7. 坐标统一解释为 `page_pixels_top_left`。页面尺寸有效时，印章区域和印章文字坐标会裁剪到
   页面范围；普通版面元素的 `layout_bbox` 和 `position` 沿用 PaddleX 坐标，不保证位于页面内。

## 当前明确不保证

1. 不保证远端缺失尺寸或正文时主动失败；归一化模型可产生 `image_width/image_height == 0`
   或空 `document_content`。严格烟测验证器会将这些结果判为质量门槛失败。

## 输出与引用

1. 顶层兼容结构及每页必需字段不得无理由重命名或删除。
2. 正文使用 `[印章N]`，机器关联使用稳定的 `seal_id=page-<页码>-seal-<序号>`。
3. `content_references.target_id` 必须等于对应 `seal_id`。
4. 引用偏移采用 Python 右开切片语义，必须满足 `document_content[start_offset:end_offset] == token`。
5. 不依赖 `document_details` 数组下标建立正文引用。

完整字段结构由 `src/pdf_parser/models.py` 和相关测试定义；本文件不复制 Pydantic 字段清单。
