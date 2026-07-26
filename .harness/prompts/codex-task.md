# Codex Task Prompt Template

```markdown
先阅读根目录 `AGENTS.md`，再阅读与任务相关的 `.harness/` 文件。

任务：
<描述期望结果>

影响范围：
<CUDA / 昇腾 / 两个平台 / Pipeline / VLM / 文档 / 压测>

约束：
- 当前 CUDA 和昇腾配置已经实机验证。
- 核心架构是一个 PaddleOCR API/PP-DocLayout 前道加多个 vLLM 模型实例。
- 保留用户的无关改动。
- 修改应局部、明确，不做无关升级或重构。
- 配置、环境变量示例和文档保持一致。
- 缺少目标硬件时不要声称完成实机验证。

期望验证：
<列出静态检查、Compose 检查、接口检查或压测证据>
```
