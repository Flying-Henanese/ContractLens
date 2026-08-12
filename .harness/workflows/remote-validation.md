# Remote Validation Workflow

远端能力会随服务重启、YAML 和模型变化。涉及服务参数、协议或真实归一化时：

1. 运行 `uv run pdf-parser health`，不要仅依据历史文档。
2. 必要时读取 `/openapi.json`，从去除 Base64 的响应摘要核对 `model_settings` 和印章参数。
3. 使用 `.harness/scripts/smoke.ps1`，输出只能写入 `output/smoke/`。
4. 区分冷启动和预热结果，不把单次性能数据硬编码为客户端事实。
5. 使用 `validate_result.py` 检查严格烟测质量门槛：JSON 可解析、至少一页、正文非空、页面
   尺寸为正、坐标在页面内且印章引用一致；另外人工或定向脚本检查页数与输入一致及表格 HTML
   完整。该验证器有意比生产 Pydantic 模型更严格，失败表示烟测验收未通过，不等同于模型
   结构解析必然失败。
6. 观测发生变化时更新 `operations/remote-state.md` 或 `operations/baselines.md`，注明日期、端点和证据。

需要先部署本仓库代码到 T4 服务器时，遵循
[`remote-deploy-and-smoke.md`](remote-deploy-and-smoke.md)，目标目录和端口见
[`../operations/remote-targets.md`](../operations/remote-targets.md)。

远端不可用时报告未验证项，不用 mock 结果替代真实集成结论。
