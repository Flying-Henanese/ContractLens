# Remote State

本文件记录会过期的远端运行观测，不是客户端配置或永久产品规格。每次依赖这些信息前必须重新运行健康检查并核对实际响应。

## 最近观测

观测日期：2026-09-11（只读复核）

远端工作区位于 `codex/unify-inference-stack`，提交为 `5dfebe4`，工作区干净。执行
`bash scripts/docker.sh ps` 未列出任何容器；对 `127.0.0.1:8888/openapi.json` 和
`127.0.0.1:8880/health` 的本机请求均被拒绝连接。该记录只说明复核时统一栈没有运行，未对
其执行启动、重建、清理或修复操作。

部署或真实烟测前必须按远端工作流重新检查可用 GPU、端口和容器状态；不得把下述历史成功验证
当作当前在线状态。

## 历史观测（2026-09-11，统一 Compose CUDA 验证）

在同一分支和提交 `5dfebe4` 上，预检确认目标端口 `8888`、`8880`、`8118` 可用，且网关、PaddleX
与 vLLM 所需镜像已存在。未重建镜像：Dockerfile、锁定依赖和镜像参数没有变化，使用现有镜像由
`bash scripts/docker.sh up` 创建统一栈。

`bash scripts/docker.sh config`、`up` 和 `ps` 均成功。`api`、`paddleocr-vl-api`、
`paddleocr-vlm-server` 三个容器均达到 healthy；网关的 `/openapi.json` 和 PaddleX 的 `/health`
均返回成功。使用临时的一页含文本 PDF 通过 PaddleX 端点执行 `pdf-parser parse`，生成的结果经
`validate_result.py` 契约校验通过。临时输入未保存到仓库，烟测结果仅写入 `output/smoke/`。

该次运行结束时，Pipeline 使用 GPU 4，vLLM 使用 GPU 5、6；其余 T4 GPU 空闲。这是一次启动、
连通性和最小真实解析验证，不代表性能基线、模型质量比较或 Ascend 验证已经完成。

## 历史观测（2026-07-29，合并前部署）

部署状态：用户确认 T4 已切换到 Docker Compose，FastAPI 镜像已成功构建且容器正在运行。
该确认只覆盖部署方式和一次成功启动，不替代每次发布前的 `docker compose ps`、容器健康
状态、日志及 HTTP 端点检查。

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
