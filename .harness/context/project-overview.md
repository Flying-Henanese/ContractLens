# Project Overview

## 项目用途

本项目将 PaddleOCR-VL-1.6 组织为高并发文档解析服务，支持 NVIDIA CUDA 和
华为昇腾 NPU。两套配置均已完成实机运行验证。

目标架构是一个前道 PaddleOCR API/PP-DocLayout 服务加多个后端 vLLM 模型
实例。前道将文档拆成大量版面子任务，后端并行消费这些任务，以提高大规模
文档处理吞吐。

项目主要负责服务编排、任务扇出和并发参数协同，不自行实现 OCR 模型、HTTP
框架或推理引擎。

## 核心能力

- 接收 PDF、图片或 TIFF，并通过 `/layout-parsing` 返回版面解析结果。
- 使用 PP-DocLayoutV3 完成文档预处理和版面分析。
- 将版面子图并发提交给 PaddleOCR-VL-1.6-0.9B。
- 使用 vLLM 数据并行，在多张 GPU/NPU 上加载多个完整模型实例。
- 结合外层文档并发、版面子图并发和 vLLM 连续批处理实现大规模并行处理。
- 提供 CUDA 与昇腾 Docker Compose 部署。
- 提供已有 uv 环境下的 CUDA 启动脚本。
- 提供标准库实现的轻量并发压测脚本。

## 主要文件

- `compose.yaml`：CUDA 双服务部署。
- `compose.ascend.yaml`：昇腾双服务部署。
- `PaddleOCR-VL-1.6.yaml`：Pipeline 拓扑和并发配置。
- `vllm_config.yaml`：vLLM 数据并行及调度配置。
- `.env.example`：CUDA 示例参数。
- `.env.ascend.example`：昇腾示例参数。
- `docker/vlm-entrypoint.sh`：CUDA VLM 容器入口。
- `docker/vlm-entrypoint-ascend.sh`：昇腾 VLM 容器入口。
- `start_vl.sh`：宿主机 CUDA 双进程启动器。
- `scripts/benchmark.py`：服务压测工具。
- `README.md`：CUDA 和通用说明。
- `ASCEND.md`：昇腾部署说明。

## 非主链路文件

`PP-StructureV3-cuda.yaml` 和 `start.sh` 是独立的 PP-StructureV3 实验入口，
不参与 PaddleOCR-VL 多实例主链路。修改时不要混淆两套配置。

## 成功标准

- 单个前道服务能够持续向后端生成和分发版面子图任务。
- 多个 VLM 模型实例均能稳定加载并实际承担推理负载。
- 随文档并发和 VLM 实例数增加，整体请求/页吞吐在资源边界内获得可测收益。
- 高负载下错误率、OOM、超时和尾延迟处于可接受范围。
- CUDA 与昇腾保持相同的逻辑架构和配置语义。
