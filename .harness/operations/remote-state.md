# Remote State

本文件记录会过期的远端运行观测，不是客户端配置或永久产品规格。每次依赖这些信息前必须重新运行健康检查并核对实际响应。

## A100 最近观测（2026-11-13）

服务器`a100`/192.168.0.194，目录`/home/mineru_dev/github/contractlens`。
分支`codex/two-gpu-colocated-deployment`，构建及运行验证时代码`8014d7a`；工作区干净。
A100 80GB PCIe×4，112逻辑CPU、755GiB RAM、驱动550.54.15、Docker Compose2.29.1。
只使用原空闲GPU2/3：pipeline-1可见2，pipeline-2可见3，VLM可见2,3、TP1/DP2/mp；
显存比例0.6、max-num-seqs16、max-num-batched-tokens16384，每worker子图并发16。
`bash scripts/docker-two-gpu.sh ps`及docker inspect确认五服务healthy，OOM=false、restart=0。
GPU0/1显存保持65449/52424MiB，其运行服务未修改。

使用仓库Dockerfile实际构建`pdf-parser:two-gpu`，image ID
`sha256:351750316a2196a65d004edf3b28e504b638cac7a295dc495c30c3de1350638f`。
首次BuildKit软nofile1024导致uv标准库字节码编译EMFILE；共置overlay的构建专属nofile65536修复后构建通过。
没有改宿主限制、驱动、Dockerfile、Ascend或其他服务。
推理镜像从T4复制后补齐原registry digest引用，内容ID为Pipeline44e5147cab1d、VLM58736a123d9c，与T4一致。
一次性内网传输监听已关闭。

宿主`.paddlex/official_models`是指向`/nas_data/models/paddlex`的绝对软链接，容器内不可达。
首次初始化因此尝试下载，随后主动down终止（143，非崩溃），改为实目录缓存再up。
当前`.env.two-gpu`的`PADDLEX_CACHE_DIR`为
`/home/mineru_dev/github/contractlens/tmp/paddlex-cache`，包含4个所需模型。
**当前运行依赖此目录，不得将其随临时PDF清理。** 原NAS模型文件未修改。
权重model.safetensors SHA256为85a479d506a11e724e7285d395c551be69f41dbc16b6342d3cacfb189aed71db，
宿主与容器内均已核对，与T4一致。

健康端点8888/openapi.json、8880/health、8118/v1/models均返回成功。
最初两行合成PDF返回200但正文为空，严格校验失败；源文件可提取73字符，未隔离确定模型根因，保留失败记录。
改用上一轮同一书籍第30页的单页PDF，经8888业务API返回200、1页并通过严格契约校验。
两个DP均有生成token计数，完成后running/waiting为0；未运行整书或性能基准，不宣称A100性能验收。
原始结果及部署摘要仅在远端`output/smoke/a100-deploy-2026-11-13/`。

## T4 最近观测

观测日期：2026-11-13（双卡共置模拟V100，实际T4）

分支`codex/two-gpu-colocated-deployment`，测量时代码`87c5645`，远端工作区干净。
使用独立`.env.two-gpu`及`bash scripts/docker-two-gpu.sh ps`检查：
api、paddleocr-vl-api（Nginx）、pipeline-1/2、paddleocr-vlm-server全部healthy。
已通过docker inspect和nvidia-smi确认Pipeline1/GPU2、Pipeline2/GPU3，VLM可见2,3、TP1/DP2/mp。
显存比例0.6，max-num-seqs16、max-num-batched-tokens16384，每worker子图并发16。
旧`.env`保留四worker方案参数未改，Ascend未改。

固定样本48/48成功且严格校验通过，中位0.41742页/s。整书按用户要求提前停止，
保留231条完成记录、223成功、8超时；GPU2/3区间平均76.62%/48.71%，偏载与长尾尚在。
三个推理容器OOMKilled=false、restart=0。未补跑8888网关真实解析烟测，不作为V100验收。
证据及限制见[双卡报告](../reports/benchmarks/2026-11-13-two-gpu-colocated.md)，
配置步骤见[部署手册](../../deploy/two-gpu/README.md)。

## 历史观测（2026-11-13，T4 CUDA 四 Pipeline 配置，已被双卡方案替代）

观测日期：2026-11-13（T4 CUDA 四 Pipeline 配置）

远端目录 `/home/mineru_dev/projects/ContractLens` 位于分支
`codex/t4-pipeline-replicas-benchmark`，提交 `296f5f1`，工作区干净。
`bash scripts/docker.sh ps` 显示 `api`、Nginx 服务 `paddleocr-vl-api`、共享
`paddleocr-vlm-server` 和 `pipeline-1` 至 `pipeline-4` 全部 healthy。

该次运行的 `.env` 参数为 Pipeline GPU 1，vLLM GPU 2/3/4/5、TP=1、DP=4、backend=mp、
显存比例 0.6、每 rank max-num-seqs=16、max-num-batched-tokens=16384；4 个 Pipeline
容器均使用 GPU 1 和 `PIPELINE_SUBGRAPH_CONCURRENCY=16`。vLLM 使用
PaddleOCR-VL-1.6-0.9B，Pipeline 与 vLLM 版本为 PaddleX 3.6.1、vLLM 0.10.2。

整书性能记录和验收限制见[基准报告](../reports/benchmarks/2026-11-13-t4-pipeline-replicas.md)。
这次记录只对应上述分支和观测时间；部署前仍须检查远端分支、工作区、GPU、参数及容器健康。

历史观测日期：2026-09-11（只读复核）

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
