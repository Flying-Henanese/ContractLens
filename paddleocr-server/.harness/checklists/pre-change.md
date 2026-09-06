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
- 确认设备列表数量与数据并行模型实例数仍然一致。容器 VLM entrypoint 会在
  启动时检查这一项，但 `docker compose config` 不会检查。
- 确认 Pipeline 与 VLM 不会使用同一物理设备。`start_vl.sh` 会检查 CUDA
  重叠；CUDA/昇腾 Compose 当前不会检查两组设备是否重叠。
- 确认改动属于客户端请求压力、单次 Pipeline 内部队列、子图请求并发、实例内
  批处理或模型实例扩展中的哪一层。当前普通 `paddlex --serve` 服务契约一次
  处理一个 HTTP 请求。
- 使用 `layout_prep_cpu_workers` 前确认目标镜像中的 PaddleX 版本确实读取该
  字段；不能只根据 YAML 中存在字段就认定线程池已启用。
- 避免无关重构、依赖升级、镜像升级和批量格式化。
- 架构或部署契约变化先在 `.harness/designs/` 记录设计。
- 多步骤或需跨会话继续的任务在 `.harness/plans/` 记录计划。
