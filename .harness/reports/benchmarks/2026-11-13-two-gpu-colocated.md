# 双卡共置：2 Pipeline worker + vLLM DP=2

日期：2026-11-13。用户要求提前停止整书压测；当前结果已封存，未追加推理请求。

## 环境与复现

用户授权在现有T4模拟目标双V100拓扑。实际仅使用宿主GPU2、3，每张15,360MiB。
Pipeline1/GPU2、Pipeline2/GPU3；VLM可见2,3，TP1、DP2、mp；不是固定请求配对。
其他GPU上的服务未改动。远端部署目录 `/home/mineru_dev/projects/ContractLens`，
分支 `codex/two-gpu-colocated-deployment`，测量时代码 `87c5645`。

独立 `.env.two-gpu`，入口 `scripts/docker-two-gpu.sh`；旧 `.env` 保留未改。
vLLM显存预算0.6、max-num-seqs16、max-num-batched-tokens16384，每worker子图并发16。
API网关页并发2、重试0；独立页基准客户端并发8、总超时120s、不重试。
模型、Pipeline及vLLM镜像与上一轮保持一致，digest固定见
[环境模板](../../../deploy/two-gpu/env.template)。网关复用现有 `pdf-parser:validation-b82488d`，
通过只读挂载加载当前src；无镜像输入改动，因此未重建网关镜像。
vLLM0.10.2、Torch2.8.0+cu128（编译目标含sm70/sm75）、FP16、FlexAttention。
五个服务均通过健康检查，实际设备映射已由inspect及nvidia-smi进程核实。

同一407页PDF，SHA256
`dd200b826db5f0bd78322944a4f341ec7dfe9fb0bb46ff244adee8769dba25e1`，
远端只读原输入 `tmp/pdfs/book.pdf`；拆页仍位于tmp/pdfs，结果位于output/smoke。
未修改/分发用户PDF，代码包不含任何真实解析正文。

实际基准命令：

```bash
BENCHMARK_CLIENT_IMAGE=pdf-parser:validation-b82488d bash scripts/benchmark_two_gpu.sh colocated-2dp
```

先4页预热，再3轮固定16页，最后整书407个独立单页请求。
预热4/4成功，76.45s，首请求48.48s、第二请求64.28s；预热不计入吞吐对照。

## 固定样本

页码：1,2,3,6,7,8,30,40,80,120,160,200,240,280,320,360。

| 轮次 | 成功/严格通过 | 时间(s) | 成功页/s | P95(s) | GPU2/3平均负载 | GPU2/3显存峰值(MiB) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 16/16 | 43.926 | 0.36425 | 26.537 | 65.09% / 44.09% | 11271 / 10195 |
| 2 | 16/16 | 38.331 | 0.41742 | 23.206 | 72.19% / 53.65% | 11287 / 10275 |
| 3 | 16/16 | 36.454 | 0.43891 | 21.313 | 66.10% / 56.86% | 11173 / 10853 |

中位吞吐0.41742页/s，三轮48/48成功且严格校验通过。第二轮DP0/1平均running2.55/1.90、
waiting均0，合计生成155.43token/s；仍未证明持续饱和。
共置GPU利用率含Pipeline与VLM两类进程，不能当作纯VLM进程利用率。

## 整书提前停止（不能作为整书通过）

用户明确要求无需解析完整本书后，停止唯一基准客户端容器，没有停止或重启推理服务。
客户端由docker stop终止，退出137来自人工停止，不是推理容器OOM。
原始pages.jsonl保留231条完成记录；未生成完整summary.json，单独补记partial-summary.json，
状态为interrupted_by_user。记录页为1..230及232；其余176页缺少完成记录，
包含在途被中断和未提交页，不能统一称为“未提交”或“失败”。

| 指标 | 已记录区间结果 |
| --- | --- |
| 完成记录 | 231 |
| 成功 | 223 |
| 超时 | 8 |
| 严格校验通过 | 215 |
| 已知空白页严格正文门槛失败 | 4,12,70,116,118,156,214,216 |
| 观测区间 | 721.28s |
| 区间成功页/s（不是整书吞吐） | 0.30917 |
| 完成记录P50/P95/P99 | 17.59 / 69.14 / 120.00s |
| GPU2/3平均负载 | 76.62% / 48.71% |
| GPU2/3显存峰值 | 11209 / 12031MiB |
| DP0/1平均running | 2.61 / 2.09 |
| DP0/1最大running | 14 / 13 |
| DP0/1平均及最大waiting | 均0 |
| DP0/1生成速率 | 77.52 / 65.61token/s |

超时页81、83、85、87、101、103、104、106，均为120s总时限且超时后后端健康。
空白页与上一轮已确认的源PDF空白页一致，不能把正文空白当成OCR正确率损失。
GPU负载采样为整卡（Pipeline+VLM），1s目标间隔实际受HTTP与nvidia-smi耗时影响。
两个DP平均waiting=0，没有持续队列堆积；不支持“两卡持续满载”的结论。
不能用这段区间数据直接对比上一轮407页整书吞吐，也未解决长尾或偏载。

最终5个服务healthy，三个推理容器OOMKilled=false、restart=0；停止后不再追加请求。
本轮只做了健康检查与Pipeline协议基准；8888业务网关的CLI/API真实解析烟测未执行，
按用户停止测试的最新要求不再补跑。部署手册提供了后续现场执行的方法。

## 静态门槛与交付

56项离线测试通过，Harness校验、Ruff格式/静态检查、Bash语法与Compose配置检查通过。
本机没有PowerShell，未执行check.ps1本体；执行了其Harness/Ruff/pytest等价检查。
未重建镜像输入未变的网关，V100也未实测。源代码包固定提交并带内外SHA256校验，
包含Dockerfile、依赖锁、三份CUDA Compose及部署手册，不含模型、镜像层、环境密钥、用户PDF或完整响应。


## 中途负载不均衡观测

用户观察GPU2长期较忙、GPU3较空。一次同刻采样：GPU2=97%、GPU3=4%，
DP0 running3、DP1 running0，两rank waiting均0；随后60s窗口GPU2/3均值96.93%/25.96%。
三个推理容器healthy、OOMKilled=false、restart=0，DP1此前有成功生成记录，因此不是漏启一个DP。
发生在81页及相邻请求超时期间；随后pipeline-1恢复返回，127页后两个worker再次同时有完成记录。

镜像内 `vllm/v1/engine/core_client.py::DPLBAsyncMPClient.get_core_engine_for_request`
按 `4 * waiting + running` 选择rank，约100ms更新状态，不使用实际GPU利用率或请求剩余token估计。
Pipeline串行页面保护、长VLM生成及请求成本差异可以造成偏载；这些是机制与关联证据，
不声称已经隔离证明唯一根因，也没有在本轮中途修改DP调度、绑定或并发来消除偏载。

当前压测是8个在途单页请求直接访问8880 Pipeline入口；8888 FastAPI网关压测并发为0。
生产网关的PDF_PARSER_CONCURRENCY=2不控制这个独立客户端；业务API烟测将单独记录。

## V100适用性边界

拓扑与显存预留方式可复用到双V100，但本报告不是V100性能或兼容验收。
Torch包含sm70只是必要证据，不代表所有Paddle/自定义算子都已在V100验证。
官方说明CC7.x的T4/V100运行vLLM可能超时/OOM：
[PaddleOCR文档](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html)。
现场需按[部署手册](../../../deploy/two-gpu/README.md)验收实际镜像、缓存、dtype、GPU映射、显存和真实PDF。
