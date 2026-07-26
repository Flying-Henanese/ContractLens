# Pre-Change Checklist

修改代码、脚本、配置或文档前执行：

- 阅读根目录 `AGENTS.md`。
- 检查 `git status --short`，保留用户已有的无关改动。
- 确认任务属于 CUDA、昇腾、两者共用部分，还是旧 PP-StructureV3 入口。
- 涉及 CUDA 时核对 `README.md`、`compose.yaml` 和 `.env.example`。
- 涉及昇腾时核对 `ASCEND.md`、`compose.ascend.yaml` 和
  `.env.ascend.example`。
- 涉及 VLM 时同时检查 entrypoint、`vllm_config.yaml` 和环境变量。
- 涉及 Pipeline 时检查 `PaddleOCR-VL-1.6.yaml` 与实际 VLM 地址。
- 涉及并发、吞吐或扩容时先阅读 `context/concurrency-model.md`。
- 确认设备列表数量与数据并行模型实例数仍然一致。
- 确认 Pipeline 与 VLM 不会使用同一物理设备。
- 确认改动属于文档并发、子任务并发、实例内批处理或模型实例扩展中的哪一层。
- 避免无关重构、依赖升级、镜像升级和批量格式化。
- 架构或部署契约变化先在 `.harness/designs/` 记录设计。
- 多步骤或需跨会话继续的任务在 `.harness/plans/` 记录计划。
