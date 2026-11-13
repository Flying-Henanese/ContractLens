---
status: active
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
3. 固定样本及整书独立页基准、GPU/DP 采样、网关烟测，记录失败和显存峰值。
4. 手册说明 GPU 编号、模型缓存、镜像、V100 现场验收、回滚和在线/离线部署边界；打包并验包。

## 验证与验收

Compose 确认 worker-1/GPU-A、worker-2/GPU-B，VLM可见A,B、DP2；五个服务健康。
不重试独立页，120s超时，只有健康后端超时允许继续；整书失败不伪装成功。
吞吐、各rank运行/等待、GPU负载与显存分别记录；目标V100未实测则显式标注。

## 进度记录

- 已确认现有 T4 工作区干净，创建独立分支；选用宿主 GPU 2、3。

## 意外发现

- 官方文档注明 T4/V100 可启动 vLLM，但可能超时/OOM，不建议无验收直接用于生产。

## 决策记录

- 显存比例从0.6开始，保留已有模型和推理参数；DP rank 与 Pipeline 不固定请求配对，共享VLM服务调度。

## 恢复与回滚

用 scripts/docker-two-gpu.sh down 停止共置栈；旧 .env 保留，用原 replicas/4workers 命令恢复。

## 结果总结

实施中。
