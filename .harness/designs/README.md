# Designs

当改动影响架构、服务边界、设备分配、配置契约、API 行为或平台兼容性时，
在本目录保存设计说明。

## 当前设计

- `2026-07-25-use-queues-pipeline.md`：解释 `use_queues` 启用的输入、CV、VLM
  内部队列流水线，以及它和外层并发、vLLM 并行之间的关系。

文件名：

```text
YYYY-MM-DD-short-topic.md
```

建议结构：

```markdown
# 标题

## 问题
## 当前行为
## 设计方案
## CUDA 影响
## 昇腾影响
## 兼容性与风险
## 验证方案
```
