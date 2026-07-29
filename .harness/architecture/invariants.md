# Stable System Invariants

本文件只记录跨模块、必须长期保持的行为。具体请求粒度等正在迁移的行为，以当前实现、测试和 active plan 共同判断，不在此重复固化。

## 输入、编排与失败

1. 输入 PDF 必须在本地校验；加密、空或损坏 PDF 抛出 `InvalidPdfError`。
2. 页码从 1 开始，最终输出按 `page_num` 排序且页码唯一。
3. 远端响应页数必须与本地输入页数一致。
4. 当前采用 fail-fast：任一远端或归一化失败导致整份文档失败，不写伪成功结果。

## PaddleX 边界

1. PDF 请求显式包含 `fileType=0`、`visualize=false`、`useLayoutDetection`（默认 `true`）和可配置的 `layoutThreshold`。
2. 成功响应必须满足 HTTP 200、`errorCode == 0` 和预期的 `layoutParsingResults` 形状。
3. 传输错误和超时可以重试；明确业务错误不盲目重试。
4. 错误包含可定位的文档或页码上下文，但不包含 Base64、完整响应或敏感正文。
5. 远端启用能力和模型阈值属于运行观测，不得硬编码成客户端永久事实。

## 归一化与坐标

1. 正文依次从版面块、块内整体 OCR、整体 OCR 和 Markdown 文本回退。
2. 同一物理印章对应一个 `SealDetail`；物理区域来自版面检测，`seal_res_list` 是可选文字来源。没有印章 OCR 结果时仍输出区域、ID 和引用，`texts=[]`。
3. `rec_texts[i]` 与同下标的 `rec_scores[i]`、`rec_polys[i]` 配对；仅在缺少 `rec_polys` 时回退 `rec_boxes`，不使用 `dt_polys` 配对识别文本。
4. 印章局部 polygon 只有取得可靠 `crop_bbox` 后才能逐点平移到页面坐标：`page_x = local_x + crop_bbox.x0`，`page_y = local_y + crop_bbox.y0`。
5. 每枚印章独立按服务端显式 `crop_bbox`、Markdown 图片键、版面检测印章框的顺序选择裁剪框；后两种来源只有在区域数量与识别结果数量一致时才能按原始下标绑定。
6. 多印章先按原始顺序绑定结果与区域，再按 `(y0, x0)` 视觉排序编号；数量不一致时保留文字和引用，但区域及文字坐标留空。
7. 页面尺寸、`layout_bbox` 和 `position` 均使用 `page_pixels_top_left` 坐标系并位于页面内。

## 输出与引用

1. 顶层兼容结构及每页必需字段不得无理由重命名或删除。
2. 正文使用 `[印章N]`，机器关联使用稳定的 `seal_id=page-<页码>-seal-<序号>`。
3. `content_references.target_id` 必须等于对应 `seal_id`。
4. 引用偏移采用 Python 右开切片语义，必须满足 `document_content[start_offset:end_offset] == token`。
5. 不依赖 `document_details` 数组下标建立正文引用。

完整字段结构由 `src/pdf_parser/models.py` 和相关测试定义；本文件不复制 Pydantic 字段清单。
