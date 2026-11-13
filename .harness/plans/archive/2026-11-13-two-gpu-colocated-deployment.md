---
status: completed
owner: Codex
created: 2026-11-13
updated: 2026-11-13
scope:
  - deployment
  - inference
  - delivery
supersedes: []
blocked_by: []
---

# 双卡共置部署与交付

## 目标与用户价值

在现有 T4 两张卡模拟双 V100 目标拓扑：每卡一个 Pipeline worker、一个 vLLM DP rank，TP=1、DP=2。
复用之前 407 页 PDF 验证，交付代码、Dockerfile、Compose、运维手册和可校验的压缩包。

## 当前事实与约束

从 f236d48 创建 codex/two-gpu-colocated-deployment；原工作树和 Ascend 配置不动。
用户明确同意先在 T4 验证，不能据此宣称 V100 已验收。官方提示 CC7.x vLLM 存在超时/OOM风险。
四 worker + DP4 历史配置保留可回滚。真实输入与响应不进入代码交付包。

## 实施阶段

1. 新增可选共置 overlay、两卡环境模板和统一生命周期入口。
2. 本地门槛通过、推送分支、远端干净检查并 fast-forward；使用两张卡启动。
3. 固定样本及整书独立页基准、GPU/DP采样；用户后来要求提前停止，整书保留部分记录，不追加网关烟测。
4. 手册说明 GPU 编号、模型缓存、镜像、V100 现场验收、回滚和在线/离线部署边界；打包并验包。

## 验证与验收

Compose 确认 worker-1/GPU-A、worker-2/GPU-B，VLM可见A,B、DP2；五个服务健康。
不重试独立页，120s超时，只有健康后端超时允许继续；整书失败不伪装成功。
吞吐、各rank运行/等待、GPU负载与显存分别记录；目标V100未实测则显式标注。

## 进度记录

- 已确认现有T4工作区干净，创建独立分支；选用宿主GPU2、3。
- 两卡入口、独立环境模板、共置overlay、GPU选择保护已落地并远端验证；5服务健康。
- 三轮样本48/48成功且严格校验通过，中位0.41742页/s。
- 用户要求无需完整解析整书，停止客户端；231条完成记录，223成功、8超时，不补跑网关解析烟测。
- 56项离线测试、Harness/Ruff、Bash、Compose检查通过；无PowerShell，运行check.ps1等价命令。
- 整理源码、Dockerfile、Compose、GPU配置手册，压缩包通过逐文件完整性验证。

## 意外发现

- 官方文档注明 T4/V100 可启动 vLLM，但可能超时/OOM，不建议无验收直接用于生产。

## 决策记录

- 显存比例从0.6开始，保留已有模型和推理参数；DP rank 与 Pipeline 不固定请求配对，共享VLM服务调度。

## 恢复与回滚

用 scripts/docker-two-gpu.sh down 停止共置栈；旧 .env 保留，用原 replicas/4workers 命令恢复。

## 结果总结

按用户收窄后的验证范围完成交付；不代表原始整书无超时门槛通过。
保留2 Pipeline + DP2部署，未改Ascend。V100尚未实测，偏载与长尾未修复。
完整证据见[双卡报告](../../reports/benchmarks/2026-11-13-two-gpu-colocated.md)，
交付步骤见[部署手册](../../../deploy/two-gpu/README.md)。
