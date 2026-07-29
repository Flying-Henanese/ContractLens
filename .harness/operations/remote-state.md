# Remote State

本文件记录会过期的远端运行观测，不是客户端配置或永久产品规格。每次依赖这些信息前必须重新运行健康检查并核对实际响应。

## 最近观测

观测日期：2026-07-29

端点：`http://192.168.0.67:8880/layout-parsing`

使用真实印章图片的 A/B 请求显示：基线请求有 14 个版面框但没有 seal；显式发送
`useLayoutDetection=true`、`layoutThreshold=0.5` 后有 15 个版面框，其中一个 seal 的
`score=0.8741052746772766`。使用单页 PDF 和 `fileType=0` 的同参数请求返回一个 seal：
`score=0.9355565309524536`、`coordinate=[592,0,861,222]`；同页
`parsing_res_list` 有 seal 块但没有 score 字段，`seal_res_list` 不存在。

该观测证明当前远端可从 `layout_det_res.boxes[label=seal]` 提供区域和置信度，不证明
0.5 是所有文档的最优阈值。

## 历史观测（2026-07-22）
项目默认地址：`http://192.168.0.194:8080`

最近一次在线验证显示：

- `use_doc_preprocessor: true`
- `use_seal_recognition: true`
- `use_table_recognition: true`
- `use_formula_recognition: true`
- `use_chart_recognition: true`
- `use_region_detection: true`
- 印章检测 `thresh: 0.3`
- 印章检测 `box_thresh: 0.65`
- 印章识别 `score_thresh: 0.5`

已知表现：表格可返回包含 `rowspan` / `colspan` 的 HTML；调整后的印章参数曾纠正“育限公司”并过滤低置信度 `cl`；高置信度短噪声 `41` 仍可能保留。服务首次推理可能受模型冷启动影响。

## 更新规则

新观测必须注明日期、端点、检查命令和响应证据范围，不保存 Base64、完整响应或敏感正文。旧值保留为历史时必须明确标注失效，不能无日期覆盖。
