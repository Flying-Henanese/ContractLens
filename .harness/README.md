# Harness Guide

`.harness/` 是本项目面向编码代理的本地操作手册。它补充根目录
`AGENTS.md`，用于保存稳定的项目事实、变更约束、验证清单和可复用记录。

## 使用顺序

1. 先阅读根目录 `AGENTS.md`。
2. 根据任务阅读 `context/` 中相关文件。
3. 修改前使用 `checklists/pre-change.md`。
4. 完成前使用 `checklists/verification.md`。
5. 涉及设备、容器权限、缓存目录或外部访问时，同时使用
   `checklists/security.md`。
6. 架构级改动记录到 `designs/`，多步骤工作记录到 `plans/`。
7. 只有具备长期复用价值的实机验证或排障结论才记录到 `runs/`。

## 目录职责

- `context/`：稳定的项目事实、架构、运行环境和配置关系。
- `checklists/`：修改前、交付前及安全相关检查。
- `designs/`：架构、行为或部署契约的设计说明。
- `plans/`：可被其他代理继续执行的实施计划。
- `prompts/`：启动常见代理任务的模板。
- `runs/`：重要实机验证、迁移和排障记录。

## 事实优先级

版本库中的 Compose、入口脚本和配置模板是本项目可静态核对的事实源；容器内
PaddleOCR/PaddleX/vLLM 的实际行为还取决于镜像内容。当前镜像标签使用
`latest-*`，因此历史实机结果只能证明当时的镜像和硬件组合，不能自动证明后来
拉取的同名镜像仍具有完全相同的行为。

遇到文档、配置和实机结果不一致时，先记录实际启动方式、镜像 ID/digest、
PaddleOCR/PaddleX/vLLM 版本和目标平台，再判断是文档漂移、镜像变化还是配置
问题。Compose 能成功解析不等于运行时约束已经被校验，也不等于完成实机验证。

涉及并发、吞吐、扩容或设备利用率的任务，必须阅读
`context/concurrency-model.md`。

涉及 Pipeline 模块、版面阈值、功能开关或输出行为时，阅读
`context/pipeline-configuration.md`；涉及 vLLM 引擎、数据并行、调度、显存
或缓存时，阅读 `context/vllm-configuration.md`。
