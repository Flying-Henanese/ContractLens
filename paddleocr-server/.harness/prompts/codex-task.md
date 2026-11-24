# Codex Task Prompt Template

```markdown
先阅读根目录 `AGENTS.md`，再阅读与任务相关的 `.harness/` 文件。

任务：
<描述期望结果>

影响范围：
<CUDA / 昇腾 / 两个平台 / Pipeline / VLM / 文档 / 压测>

约束：
- 查阅根 `.harness/operations/remote-state.md` 确认已有实机证据的范围。
- 默认架构是单 PaddleX Pipeline 加多个 vLLM 模型实例，Ascend 可选两个或四个 Pipeline worker。
- 保留用户的无关改动。
- 修改应局部、明确，不做无关升级或重构。
- 配置、环境变量示例和文档保持一致。
- 缺少目标硬件时不要声称完成实机验证。
- 普通 `paddlex --serve` 的请求执行并行度以目标镜像实测为准。
- `layout_prep_cpu_workers` 是否生效取决于目标 PaddleX 版本。

期望验证：
<列出静态检查、Compose 检查、接口检查或压测证据>
```
