# Codex Task Prompt Template

```markdown
先阅读根目录 `AGENTS.md`，再阅读与任务相关的 `.harness/` 文件。

任务：
<描述期望结果>

影响范围：
<CUDA / 昇腾 / 两个平台 / Pipeline / VLM / 文档 / 压测>

约束：
- 项目文档记录 CUDA 和昇腾配置曾实机验证，但当前没有 `.harness/runs/` 证据，
  且 `latest-*` 镜像可变化；不要把历史结论当作当前镜像已验证。
- 核心架构是一个 PaddleOCR API/PP-DocLayout 前道加多个 vLLM 模型实例。
- 保留用户的无关改动。
- 修改应局部、明确，不做无关升级或重构。
- 配置、环境变量示例和文档保持一致。
- 缺少目标硬件时不要声称完成实机验证。
- 当前普通 `paddlex --serve` 一次处理一个 HTTP 请求；客户端并发不等于服务端
  文档并行度。
- `layout_prep_cpu_workers` 是否生效取决于目标 PaddleX 版本。

期望验证：
<列出静态检查、Compose 检查、接口检查或压测证据>
```
