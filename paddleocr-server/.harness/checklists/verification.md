# Verification Checklist

## 通用

- 检查所改文件的完整差异。
- 执行 `git diff --check`。
- 核对 README、示例环境变量和实际配置名称是否一致。
- 明确区分静态检查、Compose 解析和实机验证。

## 静态检查

```bash
bash -n start.sh start_vl.sh \
  docker/vlm-entrypoint.sh \
  docker/vlm-entrypoint-ascend.sh

python3 -m py_compile scripts/benchmark.py

git diff --check
```

## Compose 检查

```bash
cd ..
bash scripts/docker.sh config
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
```

## 服务检查

在目标服务器具备相应运行环境时检查：

- 记录实际镜像 ID/digest 以及 PaddleOCR、PaddleX、vLLM 版本；`latest-*` 标签
  本身不足以标识已验证运行时。

```bash
curl --fail http://127.0.0.1:8888/openapi.json
curl --fail http://127.0.0.1:8880/health
```

- VLM 的 `/v1/models` 正常。
- ContractLens 网关、单个 PaddleOCR API/PP-DocLayout 前道服务和 VLM 服务均健康。
- 分配的每张 GPU/NPU 加载了预期模型。
- 多实例场景下设备均能产生推理负载。
- `/layout-parsing` 对真实 PDF 或图片返回成功结果。

## 性能改动

- 保留输入文件、请求数、并发数和预热次数。
- 对比单实例与多实例、低客户端压力与高客户端压力；普通 `paddlex --serve`
  下不要把 `scripts/benchmark.py --concurrency` 直接解释为服务端文档并行度。
- 记录客户端并发、服务端实际同时执行的请求数、子图并发和 vLLM 调度参数。
- 记录 `use_queues`、`layout_prep_cpu_workers`、前道可用 CPU 核数，并从目标
  PaddleX 版本或运行指标确认 `layout_prep_cpu_workers` 是否真正生效。
- 记录端到端延迟、尾延迟、成功率、请求吞吐、页吞吐以及前道和各 VLM
  设备利用率。
- 检查版面块 CPU 准备阶段是否积压，并观察前道 CPU 利用率和内存占用。
- 确认前道能持续产生足够子任务，而不是只观察 VLM 是否成功加载。
- 不从单次结果或静态参数推导确定性性能结论。
