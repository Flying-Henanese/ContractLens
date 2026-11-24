# Pre-Change Checklist

修改代码、脚本、配置或文档前执行：

以下相对路径假定当前目录为 `paddleocr-server/`。

- 阅读根目录 `AGENTS.md`。
- 检查 `git status --short`，保留用户已有的无关改动。
- 确认任务属于 CUDA、昇腾、两者共用部分，还是旧 PP-StructureV3 入口。
- 涉及 CUDA 时核对根 `README.md`、`../compose.yaml` 和 `../.env.template`。
- 涉及昇腾时核对根 `../docs/container-deployment.md`、`../compose.ascend.yaml`
  和 `../.env.ascend.template`；本目录的同名 Compose 仅作历史推理参考。
- 涉及 VLM 时核对[平台启动方式](../context/runtime-and-config.md)、有效参数和环境变量。
- 涉及 Pipeline 时检查 `PaddleOCR-VL-1.6.yaml` 与实际 VLM 地址。
- 涉及并发、吞吐或扩容时先阅读 `context/concurrency-model.md`。
- 确认设备列表数量与数据并行模型实例数一致。CUDA 入口在启动时复核数量；根 Ascend
  直接启动 vLLM，预检时核对 `ASCEND_RT_VISIBLE_DEVICES`、副本设备挂载和 DP 参数。
- 默认和普通副本模式需确认 Pipeline 与 VLM 的物理设备分离。昇腾 `colocated`
  模式需确认每个 worker 和对应 rank 位于同一张物理卡，且四张卡互不重复。
- 确认改动属于客户端请求压力、单次 Pipeline 内部队列、子图请求并发、实例内
  批处理、Pipeline 副本数或模型实例扩展中的哪一层。普通 `paddlex --serve`
  的请求串行行为以目标镜像为准。
- 使用 `layout_prep_cpu_workers` 前确认目标镜像中的 PaddleX 版本确实读取该
  字段；不能只根据 YAML 中存在字段就认定线程池已启用。
- 避免无关重构、依赖升级、镜像升级和批量格式化。
- 架构或部署契约变化先在 `.harness/designs/` 记录设计。
- 多步骤或需跨会话继续的任务在 `.harness/plans/` 记录计划。
