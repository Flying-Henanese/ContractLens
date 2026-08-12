# Stable System Invariants

本文件只记录跨模块、必须长期保持的行为。具体请求粒度等正在迁移的行为，以当前实现、测试和 active plan 共同判断，不在此重复固化。

## 输入、编排与失败

1. PDF 输入必须在本地校验；加密、空或损坏 PDF 抛出 `InvalidPdfError`。当前
   `service.py::_count_pages()` 和 `ingestion/pdf.py::iter_pdf_pages()` 都会读取并校验文件。
2. 图像文档只接受 BMP、JPEG、PNG、TIFF 和 WEBP；API 同时校验扩展名、Content-Type 和
   二进制签名，`service.py::parse_image()` 会再次读取并校验签名，失败抛出 `InvalidImageError`。
3. 页码从 1 开始，最终输出按 `page_num` 排序且页码唯一；图像固定归一化为第 1 页。
4. 每个单页 PDF 或图像远端请求必须恰好返回一个 `layoutParsingResults` 条目；服务为每个本地页生成一个
   归一化页面，因此最终页数与本地页数一致。
5. 当前采用 fail-fast：任一输入、远端或归一化失败导致整份文档失败，不写伪成功结果。

## PaddleX 边界

1. PDF 请求显式包含 `fileType=0`；图像请求显式包含 `fileType=1`。两者都包含
   `visualize=false`、`useLayoutDetection`（默认 `true`）和可配置的 `layoutThreshold`。
2. 成功响应必须满足 HTTP 200、`errorCode == 0` 和预期的 `layoutParsingResults` 形状。
3. 传输错误和超时可以重试；明确业务错误不盲目重试。
4. 错误包含可定位的图像、文档或页码上下文，但不包含 Base64、完整响应或敏感正文。
5. 远端启用能力和模型阈值属于运行观测，不得硬编码成客户端永久事实。

## 归一化与坐标

1. 存在版面块时，每个非印章块先使用 `block_content`/`text`，为空且 bbox 有效时使用中心点
   落在块内的整体 OCR；不会再把块外的整体 OCR 追加为正文。只有完全没有版面详情时，才按
   整体 OCR 生成详情；组装后的正文仍为空时回退 Markdown 文本。
2. 有 `seal_res_list` 时，每个有效识别结果生成一个 `SealDetail`；没有 `seal_res_list` 时，
   每个版面印章检测框生成一个 `SealDetail`、ID 和引用，`texts=[]`。当前不合并或去重重复的
   识别结果/检测框，条目数不等同于人工确认的物理印章数。
3. `rec_texts[i]` 与同下标的 `rec_scores[i]`、`rec_polys[i]` 配对；仅在缺少 `rec_polys` 时回退 `rec_boxes`，不使用 `dt_polys` 配对识别文本。
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
